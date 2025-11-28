import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures # 병렬 처리를 위한 도구

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="주식 검색기 (고속버전)", layout="wide")

st.title("⚡️ 주식 검색기 (고속 스캔)")

# --- 2. 공지사항 ---
with st.expander("📢 검색 조건 확인하기 (클릭하여 상세 조건 보기)", expanded=False):
    st.markdown("""
    **다음의 15가지 조건을 모두 만족(AND)하는 종목을 찾습니다.**
    
    1. **제외 대상:** 거래정지, 관리/환기/주의 종목, 불성실공시, ETF, ETN, 스팩, 우선주, 홀딩스
    2. **(월봉)** 현재 캔들이 양봉(+)일 것
    3. **(주봉)** 현재 고가가 직전 봉 고가보다 높을 것
    4. **(주봉)** 현재 저가가 직전 봉 저가보다 높을 것
    5. **(일봉)** 60일 이평선 <= 120일 이평선
    6. **(일봉)** 20일 이평선 <= 60일 이평선
    7. **(일봉)** 5일 이평선 >= 10일 이평선
    8. **(일봉)** 10일 이평선 >= 20일 이평선
    9. **(일봉)** 5일 이평선 상승 또는 보합
    10. **(일봉)** 10일 이평선 상승
    11. **(일봉)** 20일 이평선 상승
    12. **(거래대금)** 120일 이내에 50억 이상 거래 터진 날이 1회 이상 있을 것
    13. **(재무)** 유보율 500% 이상
    14. **(재무)** 부채비율 150% 이하
    15. **(재무)** 최근 분기 ROE 5% 이상
    """)

st.divider()

# --- 3. 검색 설정 ---
st.subheader("🛠 검색 옵션 설정")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 1. 코스피(KOSPI)")
    use_kospi = st.checkbox("코스피 포함", value=True)
    kospi_limit = st.number_input("코스피 검색 수량", min_value=10, max_value=2000, value=50, disabled=not use_kospi)

with col2:
    st.markdown("### 2. 코스닥(KOSDAQ)")
    use_kosdaq = st.checkbox("코스닥 포함", value=False)
    kosdaq_limit = st.number_input("코스닥 검색 수량", min_value=10, max_value=2000, value=50, disabled=not use_kosdaq)

with col3:
    st.markdown("### 3. 추가 조건")
    min_money = st.number_input("최소 거래대금 (단위: 억)", value=50)
    st.caption("※ 동시 처리(병렬) 기술이 적용되어 속도가 향상되었습니다.")

total_count = 0
if use_kospi: total_count += kospi_limit
if use_kosdaq: total_count += kosdaq_limit

st.info(f"💡 현재 설정으로 **총 {total_count}개** 종목을 스캔합니다.")


# --- 4. 데이터 분석 로직 ---

def check_fundamental(code):
    """재무제표 크롤링"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3) # 타임아웃 설정
        soup = BeautifulSoup(response.text, 'html.parser')
        
        finance_html = soup.select('div.section.cop_analysis div.sub_section')
        if not finance_html: return False, {}
            
        df_fin = pd.read_html(str(finance_html[0]))[0]
        df_fin.set_index(df_fin.columns[0], inplace=True)
        
        reserve_series = df_fin.loc['유보율'].dropna()
        if reserve_series.empty: return False, {}
        reserve_ratio = float(str(reserve_series.iloc[-1]).replace(',', ''))
        
        debt_series = df_fin.loc['부채비율'].dropna()
        if debt_series.empty: return False, {}
        debt_ratio = float(str(debt_series.iloc[-1]).replace(',', ''))
        
        roe_series = df_fin.loc['ROE'].dropna()
        if roe_series.empty: return False, {}
        roe = float(str(roe_series.iloc[-1]).replace(',', ''))

        if reserve_ratio >= 500 and debt_ratio <= 150 and roe >= 5.0:
            return True, {"유보율": reserve_ratio, "부채비율": debt_ratio, "ROE": roe}
        else:
            return False, {}
    except:
        return False, {}

def analyze_stock(stock_info):
    """
    개별 종목 분석 함수
    (병렬 처리를 위해 code, name을 묶어서 하나의 인자로 받습니다)
    """
    code = stock_info['Code']
    name = stock_info['Name']

    # 1. 이름 필터
    exclusion_keywords = ["스팩", "ETF", "ETN", "홀딩스", "우"]
    for keyword in exclusion_keywords:
        if keyword in name: return None

    # 차트 데이터
    try:
        df = fdr.DataReader(code, start=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
    except:
        return None
        
    if len(df) < 120: return None 

    # 주봉/월봉
    df_week = df.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})
    df_month = df.resample('M').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})

    if len(df_week) < 2 or len(df_month) < 2: return None

    # 차트 조건 검사
    curr_day = df.iloc[-1]
    curr_week = df_week.iloc[-1]; prev_week = df_week.iloc[-2]
    curr_month = df_month.iloc[-1]; prev_month_close = df_month.iloc[-2]['Close']

    if curr_month['Close'] <= prev_month_close: return None
    if curr_week['High'] <= prev_week['High']: return None
    if curr_week['Low'] <= prev_week['Low']: return None

    ma5 = df['Close'].rolling(5).mean()
    ma10 = df['Close'].rolling(10).mean()
    ma20 = df['Close'].rolling(20).mean()
    ma60 = df['Close'].rolling(60).mean()
    ma120 = df['Close'].rolling(120).mean()
    
    # 이평선 값이 없으면(NaN) 계산 불가하므로 체크
    if ma120.isnull().iloc[-1]: return None

    c_ma5 = ma5.iloc[-1]; p_ma5 = ma5.iloc[-2]
    c_ma10 = ma10.iloc[-1]; p_ma10 = ma10.iloc[-2]
    c_ma20 = ma20.iloc[-1]; p_ma20 = ma20.iloc[-2]
    c_ma60 = ma60.iloc[-1]
    c_ma120 = ma120.iloc[-1]

    if not (c_ma60 <= c_ma120): return None
    if not (c_ma20 <= c_ma60): return None
    if not (c_ma5 >= c_ma10): return None
    if not (c_ma10 >= c_ma20): return None
    if not (c_ma5 >= p_ma5): return None
    if not (c_ma10 > p_ma10): return None
    if not (c_ma20 > p_ma20): return None

    df['Amount_Bil'] = (df['Close'] * df['Volume']) / 100000000
    if df['Amount_Bil'].tail(120).max() < min_money: return None

    # 재무 분석
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

# --- 5. 실행 버튼 (병렬 처리 적용) ---
st.divider()
if st.button("🚀 고속 검색 시작", type="primary", use_container_width=True):
    if total_count == 0:
        st.error("코스피 또는 코스닥 중 하나 이상을 선택하고 수량을 입력해주세요.")
    else:
        st.write(f"🔎 총 {total_count}개 종목을 **10개의 스레드로 병렬 분석**합니다...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        target_stocks = pd.DataFrame()
        
        if use_kospi:
            target_stocks = pd.concat([target_stocks, fdr.StockListing('KOSPI').head(kospi_limit)])
        if use_kosdaq:
            target_stocks = pd.concat([target_stocks, fdr.StockListing('KOSDAQ').head(kosdaq_limit)])
            
        target_stocks.reset_index(drop=True, inplace=True)

        # DataFrame을 딕셔너리 리스트로 변환 (병렬 처리에 넘기기 위함)
        stock_list = target_stocks.to_dict('records')
        
        # 병렬 처리 시작 (최대 10개 동시 실행)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # 작업을 예약하고 futures 객체를 받음
            futures = {executor.submit(analyze_stock, stock): stock for stock in stock_list}
            
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                stock = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    pass # 에러 발생 시 무시하고 계속 진행
                
                completed_count += 1
                
                # UI 업데이트
                progress = completed_count / len(stock_list)
                progress_bar.progress(progress)
                status_text.text(f"⏳ 분석 진행률: {int(progress * 100)}% ({completed_count}/{len(stock_list)})")

        progress_bar.empty()
        status_text.empty()
        
        if results:
            st.success(f"🎉 조건에 부합하는 {len(results)}개 종목을 발견했습니다!")
            st.dataframe(pd.DataFrame(results))
        else:
            st.warning("조건을 만족하는 종목이 없습니다.")
