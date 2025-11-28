import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="주식 검색기", layout="wide")

# 제목
st.title("📈 주식 검색기")

# --- 2. 공지사항 및 검색 조건 (열고 닫기 가능) ---
with st.expander("📢 검색 조건 확인하기 (클릭해서 펼치기/접기)", expanded=False):
    st.markdown("""
    **다음의 15가지 조건을 모두 만족(AND)하는 종목을 찾습니다.**
    
    1. **제외 대상:** 거래정지, 관리/환기/주의 종목, 불성실공시, ETF, ETN, 스팩
    2. **(월봉)** 현재 캔들이 양봉(+)일 것 (전달 종가보다 상승)
    3. **(주봉)** 현재 고가가 직전 봉 고가보다 높을 것
    4. **(주봉)** 현재 저가가 직전 봉 저가보다 높을 것
    5. **(일봉)** 60일 이평선 <= 120일 이평선
    6. **(일봉)** 20일 이평선 <= 60일 이평선
    7. **(일봉)** 5일 이평선 >= 10일 이평선
    8. **(일봉)** 10일 이평선 >= 20일 이평선 (정배열 초기)
    9. **(일봉)** 5일 이평선 상승 또는 보합
    10. **(일봉)** 10일 이평선 상승
    11. **(일봉)** 20일 이평선 상승
    12. **(거래대금)** 120일 이내에 50억 이상 거래 터진 날이 1회 이상 있을 것
    13. **(재무)** 유보율 500% 이상
    14. **(재무)** 부채비율 150% 이하
    15. **(재무)** 최근 분기 ROE 5% 이상 (연환산 기준)
    """)

# --- 3. 사이드바: 검색 옵션 설정 ---
st.sidebar.header("🔍 검색 옵션")

# 코스피 설정 (기본값: 선택됨, 50개)
use_kospi = st.sidebar.checkbox("코스피 (KOSPI)", value=True)
kospi_limit = st.sidebar.number_input(
    "코스피 검색 수량", min_value=10, max_value=2000, value=50, disabled=not use_kospi
)

# 코스닥 설정 (기본값: 선택안됨, 50개)
use_kosdaq = st.sidebar.checkbox("코스닥 (KOSDAQ)", value=False)
kosdaq_limit = st.sidebar.number_input(
    "코스닥 검색 수량", min_value=10, max_value=2000, value=50, disabled=not use_kosdaq
)

st.sidebar.markdown("---")
# 거래대금 설정 (조건 12번의 변수)
min_money = st.sidebar.number_input("최소 거래대금 기준 (단위: 억)", value=50)

# 총 검색 예상 수량 계산
total_count = 0
if use_kospi: total_count += kospi_limit
if use_kosdaq: total_count += kosdaq_limit

st.sidebar.info(f"총 {total_count}개 종목을 분석합니다.\n(재무 크롤링으로 시간이 소요됩니다)")


# --- 4. 데이터 분석 함수들 ---

# (A) 재무제표 크롤링 (네이버 금융)
def check_fundamental(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        finance_html = soup.select('div.section.cop_analysis div.sub_section')
        if not finance_html:
            return False, {}
            
        df_fin = pd.read_html(str(finance_html[0]))[0]
        df_fin.set_index(df_fin.columns[0], inplace=True)
        
        # 데이터가 존재하는 가장 최근 컬럼 찾기 (오른쪽 끝이 보통 최근)
        # 안전장치: 데이터가 없는 경우를 대비해 fillna
        
        # 13. 유보율
        reserve_series = df_fin.loc['유보율'].dropna()
        if reserve_series.empty: return False, {}
        reserve_ratio = float(str(reserve_series.iloc[-1]).replace(',', ''))
        
        # 14. 부채비율
        debt_series = df_fin.loc['부채비율'].dropna()
        if debt_series.empty: return False, {}
        debt_ratio = float(str(debt_series.iloc[-1]).replace(',', ''))
        
        # 15. ROE
        roe_series = df_fin.loc['ROE'].dropna()
        if roe_series.empty: return False, {}
        roe = float(str(roe_series.iloc[-1]).replace(',', ''))

        # 조건 검증
        if reserve_ratio >= 500 and debt_ratio <= 150 and roe >= 5.0:
            return True, {"유보율": reserve_ratio, "부채비율": debt_ratio, "ROE": roe}
        else:
            return False, {}

    except Exception:
        return False, {}

# (B) 차트 및 기술적 분석
def analyze_stock(code, name):
    # 1. 이름 필터 (스팩, ETF 등 제외)
    exclusion_keywords = ["스팩", "ETF", "ETN", "홀딩스", "우"]
    for keyword in exclusion_keywords:
        if keyword in name: return None

    # 차트 데이터 (약 1년치)
    try:
        df = fdr.DataReader(code, start=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
    except:
        return None
        
    if len(df) < 120: return None # 신규 상장주 제외

    # 주봉/월봉 생성
    df_week = df.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})
    df_month = df.resample('M').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})

    if len(df_week) < 2 or len(df_month) < 2: return None

    curr_day = df.iloc[-1]
    curr_week = df_week.iloc[-1]; prev_week = df_week.iloc[-2]
    curr_month = df_month.iloc[-1]; prev_month_close = df_month.iloc[-2]['Close']

    # 2. (월봉) 양봉
    if curr_month['Close'] <= prev_month_close: return None
    # 3. (주봉) 고가 갱신
    if curr_week['High'] <= prev_week['High']: return None
    # 4. (주봉) 저가 높임
    if curr_week['Low'] <= prev_week['Low']: return None

    # 이평선 계산
    ma5 = df['Close'].rolling(5).mean()
    ma10 = df['Close'].rolling(10).mean()
    ma20 = df['Close'].rolling(20).mean()
    ma60 = df['Close'].rolling(60).mean()
    ma120 = df['Close'].rolling(120).mean()
    
    c_ma5 = ma5.iloc[-1]; p_ma5 = ma5.iloc[-2]
    c_ma10 = ma10.iloc[-1]; p_ma10 = ma10.iloc[-2]
    c_ma20 = ma20.iloc[-1]; p_ma20 = ma20.iloc[-2]
    c_ma60 = ma60.iloc[-1]
    c_ma120 = ma120.iloc[-1]

    # 5~8. 이평선 배열 조건
    if not (c_ma60 <= c_ma120): return None
    if not (c_ma20 <= c_ma60): return None
    if not (c_ma5 >= c_ma10): return None
    if not (c_ma10 >= c_ma20): return None
    
    # 9~11. 이평선 방향성
    if not (c_ma5 >= p_ma5): return None
    if not (c_ma10 > p_ma10): return None
    if not (c_ma20 > p_ma20): return None

    # 12. 거래대금 (입력받은 min_money 억 이상)
    df['Amount_Bil'] = (df['Close'] * df['Volume']) / 100000000
    if df['Amount_Bil'].tail(120).max() < min_money: return None

    # 모든 차트 조건 통과 시 -> 재무 확인 (속도 위해 마지막에)
    is_ok, fin = check_fundamental(code)
    
    if is_ok:
        return {
            '종목명': name,
            '코드': code,
            '현재가': f"{int(curr_day['Close']):,}원",
            '등락률': f"{round(curr_day['Change']*100, 2)}%",
            '유보율': f"{fin['유보율']}%",
            '부채비율': f"{fin['부채비율']}%",
            'ROE': f"{fin['ROE']}%"
        }
    return None

# --- 5. 실행 버튼 ---
if st.button("🚀 종목 발굴 시작"):
    if total_count == 0:
        st.warning("왼쪽 사이드바에서 시장과 수량을 선택해주세요!")
    else:
        st.write(f"설정된 조건으로 {total_count}개 종목을 분석 중입니다... 잠시만 기다려주세요.")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        target_stocks = pd.DataFrame()
        
        if use_kospi:
            target_stocks = pd.concat([target_stocks, fdr.StockListing('KOSPI').head(kospi_limit)])
        if use_kosdaq:
            target_stocks = pd.concat([target_stocks, fdr.StockListing('KOSDAQ').head(kosdaq_limit)])
            
        # 인덱스 재설정 (중요)
        target_stocks.reset_index(drop=True, inplace=True)

        for i in range(len(target_stocks)):
            row = target_stocks.iloc[i]
            status_text.text(f"🔍 분석 중 ({i+1}/{len(target_stocks)}): {row['Name']}")
            
            res = analyze_stock(row['Code'], row['Name'])
            if res: results.append(res)
            
            progress_bar.progress((i + 1) / len(target_stocks))
            
        progress_bar.empty()
        status_text.empty()
        
        if results:
            st.success(f"조건을 만족하는 {len(results)}개 종목을 찾았습니다!")
            st.dataframe(pd.DataFrame(results))
        else:
            st.info("검색된 종목이 없습니다. 조건을 조금 완화하거나 검색 수량을 늘려보세요.")
