import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 1. 페이지 및 UI 설정 ---
st.set_page_config(page_title="나만의 주식 발굴기", layout="wide")
st.title("💎 조건에 딱 맞는 주식 발굴기")

# 사이드바: 시장 및 수량 선택
st.sidebar.header("🔍 검색 설정")

# 코스피 설정
use_kospi = st.sidebar.checkbox("코스피 (KOSPI)", value=True)
kospi_limit = st.sidebar.number_input(
    "코스피 검색 수량", min_value=10, max_value=2000, value=50, disabled=not use_kospi
)

# 코스닥 설정
use_kosdaq = st.sidebar.checkbox("코스닥 (KOSDAQ)", value=False)
kosdaq_limit = st.sidebar.number_input(
    "코스닥 검색 수량", min_value=10, max_value=2000, value=50, disabled=not use_kosdaq
)

# 거래대금 설정 (조건 12)
min_money = st.sidebar.number_input("최소 거래대금 (단위: 억)", value=50)

# 총 검색 예상 수량 계산 및 표시
total_count = 0
if use_kospi: total_count += kospi_limit
if use_kosdaq: total_count += kosdaq_limit

st.sidebar.markdown(f"### 📊 총 검색 예정: **{total_count}개** 종목")
st.sidebar.info("재무 정보(유보율, 부채비율 등) 크롤링이 포함되어 속도가 다소 느릴 수 있습니다.")

# --- 2. 핵심 함수: 데이터 분석 ---

# (A) 재무제표 크롤링 함수 (네이버 금융) - 조건 13, 14, 15
def check_fundamental(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 재무제표 테이블 찾기
        finance_html = soup.select('div.section.cop_analysis div.sub_section')
        if not finance_html:
            return False, {} # 재무 데이터 없음
            
        # 데이터프레임으로 변환 (판다스가 html 표를 읽어줍니다)
        df_fin = pd.read_html(str(finance_html[0]))[0]
        
        # 데이터 정리 (최근 결산, 최근 분기 찾기)
        # 보통 테이블의 맨 오른쪽이 최근 추정치거나 최근 실적입니다.
        # 인덱스 설정 등을 통해 값을 가져옵니다. (약식 구현)
        # 실제로는 컬럼명을 정확히 파싱해야 하지만, 여기서는 행 이름으로 찾습니다.
        df_fin.set_index(df_fin.columns[0], inplace=True)
        
        # 최근 결산 연도 (보통 최근 4개년치 중 마지막 확정치)
        # 데이터가 문자열일 수 있어 처리가 필요합니다.
        
        # 편의상 가장 최근 '연간' 실적 위치를 -2 (추정치 제외 전년도) 정도로 가정하거나
        # 데이터가 있는 가장 최근 컬럼을 가져오는 로직이 필요합니다.
        # 여기서는 단순화를 위해 '최근' 데이터를 가져온다고 가정합니다.
        
        # 13. 유보율 (최근 결산)
        reserve_ratio = df_fin.loc['유보율'].dropna().iloc[-1]
        
        # 14. 부채비율 (최근 결산)
        debt_ratio = df_fin.loc['부채비율'].dropna().iloc[-1]
        
        # 15. ROE (최근 분기 - 보통 분기 실적은 아래쪽 테이블에 따로 있으나, 여기선 연환산 기준을 사용)
        roe = df_fin.loc['ROE'].dropna().iloc[-1]

        # 데이터 형변환 (문자열 -> 숫자)
        reserve_ratio = float(str(reserve_ratio).replace(',', ''))
        debt_ratio = float(str(debt_ratio).replace(',', ''))
        roe = float(str(roe).replace(',', ''))

        # 조건 비교
        cond13 = reserve_ratio >= 500
        cond14 = debt_ratio <= 150
        cond15 = roe >= 5.0
        
        is_pass = cond13 and cond14 and cond15
        return is_pass, {"유보율": reserve_ratio, "부채비율": debt_ratio, "ROE": roe}

    except Exception as e:
        # print(f"재무 데이터 오류 ({code}): {e}") # 디버깅용
        return False, {}

# (B) 기술적 분석 및 전체 로직 함수
def analyze_stock(code, name):
    # 1. 제외 종목 필터 (이름 기반 1차 필터)
    # 관리종목, 환기종목 등은 별도 API 없이는 정확한 확인이 어렵지만,
    # 스팩, ETF, ETN은 이름으로 거를 수 있습니다.
    exclusion_keywords = ["스팩", "ETF", "ETN", "홀딩스", "우"] # 우선주나 지주사도 보통 제외함
    for keyword in exclusion_keywords:
        if keyword in name:
            return None

    # 차트 데이터 가져오기 (약 200일 치 - 120일 이평선 계산 위해 넉넉히)
    df = fdr.DataReader(code, start=(datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d'))
    
    if len(df) < 120: return None # 상장한지 얼마 안 된 종목 제외

    # --- 주봉, 월봉 데이터 생성 (Resampling) ---
    df_week = df.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})
    df_month = df.resample('M').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})

    # 데이터가 너무 짧으면 패스
    if len(df_week) < 2 or len(df_month) < 2: return None

    # 현재 캔들 (아직 완성 안 된 오늘/이번주/이번달 포함)
    curr_day = df.iloc[-1]
    curr_week = df_week.iloc[-1]
    prev_week = df_week.iloc[-2]
    curr_month = df_month.iloc[-1]
    prev_month_close = df_month.iloc[-2]['Close']

    # --- 조건 검사 시작 ---

    # 2. (월봉) 현재 캔들이 빨간색 (전달 종가보다 높음)
    if curr_month['Close'] <= prev_month_close: return None

    # 3. (주봉) 현재 고가 > 전주 고가
    if curr_week['High'] <= prev_week['High']: return None
    
    # 4. (주봉) 현재 저가 > 전주 저가
    if curr_week['Low'] <= prev_week['Low']: return None

    # --- 일봉 이동평균선 계산 ---
    ma5 = df['Close'].rolling(window=5).mean()
    ma10 = df['Close'].rolling(window=10).mean()
    ma20 = df['Close'].rolling(window=20).mean()
    ma60 = df['Close'].rolling(window=60).mean()
    ma120 = df['Close'].rolling(window=120).mean()
    
    c_ma5 = ma5.iloc[-1]; p_ma5 = ma5.iloc[-2]
    c_ma10 = ma10.iloc[-1]; p_ma10 = ma10.iloc[-2]
    c_ma20 = ma20.iloc[-1]; p_ma20 = ma20.iloc[-2]
    c_ma60 = ma60.iloc[-1]
    c_ma120 = ma120.iloc[-1]

    # 5. 60이평 <= 120이평
    if not (c_ma60 <= c_ma120): return None
    
    # 6. 20이평 <= 60이평
    if not (c_ma20 <= c_ma60): return None
    
    # 7. 5이평 >= 10이평
    if not (c_ma5 >= c_ma10): return None
    
    # 8. 10이평 >= 20이평
    if not (c_ma10 >= c_ma20): return None
    
    # 9. 5이평 상승 또는 보합 (현재 >= 어제)
    if not (c_ma5 >= p_ma5): return None
    
    # 10. 10이평 상승 (현재 > 어제)
    if not (c_ma10 > p_ma10): return None
    
    # 11. 20이평 상승 (현재 > 어제)
    if not (c_ma20 > p_ma20): return None

    # 12. 120일 내 50억 이상 거래대금 1회 이상
    # 거래대금 = 종가 * 거래량 (단위: 원 -> 억 환산하려면 100,000,000 나눔)
    df['Amount_Bil'] = (df['Close'] * df['Volume']) / 100000000
    # 최근 120일 데이터 자르기
    recent_120 = df['Amount_Bil'].tail(120)
    if recent_120.max() < min_money: return None

    # --- 차트 조건 통과! 이제 재무 확인 (느리므로 마지막에) ---
    is_fundamental_ok, fin_data = check_fundamental(code)
    
    if is_fundamental_ok:
        return {
            '종목명': name,
            '코드': code,
            '현재가': f"{int(curr_day['Close']):,}원",
            '유보율': f"{fin_data['유보율']}%",
            '부채비율': f"{fin_data['부채비율']}%",
            'ROE': f"{fin_data['ROE']}%",
            '차트평': "정배열 초기/역배열 말기 조건 만족"
        }
    
    return None

# --- 3. 실행 버튼 및 루프 ---
if st.button("🚀 나만의 전략으로 종목 찾기"):
    if total_count == 0:
        st.error("시장이나 수량을 선택해주세요!")
    else:
        st.write(f"분석을 시작합니다... (총 {total_count}개 종목 스캔)")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        
        # 종목 리스트 가져오기
        target_stocks = pd.DataFrame()
        
        if use_kospi:
            kospi_stocks = fdr.StockListing('KOSPI').head(kospi_limit)
            target_stocks = pd.concat([target_stocks, kospi_stocks])
            
        if use_kosdaq:
            kosdaq_stocks = fdr.StockListing('KOSDAQ').head(kosdaq_limit)
            target_stocks = pd.concat([target_stocks, kosdaq_stocks])
            
        # 반복문 실행
        for i in range(len(target_stocks)):
            row = target_stocks.iloc[i]
            code = row['Code']
            name = row['Name']
            
            status_text.text(f"분석 중 ({i+1}/{total_count}): {name}")
            
            # 분석 실행
            result = analyze_stock(code, name)
            if result:
                results.append(result)
            
            progress_bar.progress((i + 1) / len(target_stocks))
            
        progress_bar.empty()
        status_text.empty()
        
        if results:
            st.success(f"조건을 완벽하게 만족하는 {len(results)}개 종목을 발견했습니다! 🎉")
            st.table(pd.DataFrame(results))
        else:
            st.warning("아쉽게도 모든 조건을 만족하는 종목이 없습니다. 조건을 조금 완화해보세요.")

