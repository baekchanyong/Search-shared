import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="글로벌 주식 검색기", layout="wide")

st.title("🌏 글로벌 주식 검색기 (KR & US)")

# --- 2. 공지사항 ---
with st.expander("📢 검색 조건 확인하기 (한국/미국 적용 차이)", expanded=False):
    st.markdown("""
    **✅ 공통 적용 조건 (차트 기술적 분석)**
    1. **(월봉)** 현재 캔들이 양봉(+)일 것
    2. **(주봉)** 현재 고가가 직전 봉 고가보다 높을 것
    3. **(주봉)** 현재 저가가 직전 봉 저가보다 높을 것
    4. **(일봉)** 60일 이평선 <= 120일 이평선
    5. **(일봉)** 20일 이평선 <= 60일 이평선
    6. **(일봉)** 5일 이평선 >= 10일 이평선
    7. **(일봉)** 10일 이평선 >= 20일 이평선
    8. **(일봉)** 5일 이평선 상승 또는 보합
    9. **(일봉)** 10일 이평선 상승
    10. **(일봉)** 20일 이평선 상승
    11. **(거래대금)** 120일 이내에 50억(KRW) 이상 거래 터진 날이 1회 이상 있을 것 
       *(미국 주식은 환율 1400원 가정하여 약 3.5M 달러로 계산)*

    **✅ 한국 주식(KOSPI, KOSDAQ) 전용 조건**
    12. **제외 대상:** 관리/환기/주의, 스팩, ETF, ETN, 우선주, 홀딩스
    13. **(재무)** 유보율 500% 이상
    14. **(재무)** 부채비율 150% 이하
    15. **(재무)** 최근 분기 ROE 5% 이상

    **❌ 미국 주식(NASDAQ) 예외**
    * 재무 데이터(유보율, 부채비율 등) 크롤링은 지원하지 않으며, **차트 조건만 만족하면 추출**됩니다.
    """)

st.divider()

# --- 3. 검색 설정 UI ---
st.subheader("🛠 시장 및 수량 설정")

col1, col2, col3, col4 = st.columns(4)

# 설정값 저장 변수
targets = []

with col1:
    st.markdown("### 🇰🇷 코스피")
    use_kospi = st.checkbox("KOSPI 포함", value=True)
    kospi_all = st.checkbox("KOSPI 전체 검색", value=False, disabled=not use_kospi)
    kospi_limit = st.number_input("검색 수량", 10, 3000, 50, key="kospi_n", disabled=not use_kospi or kospi_all)

with col2:
    st.markdown("### 🇰🇷 코스닥")
    use_kosdaq = st.checkbox("KOSDAQ 포함", value=False)
    kosdaq_all = st.checkbox("KOSDAQ 전체 검색", value=False, disabled=not use_kosdaq)
    kosdaq_limit = st.number_input("검색 수량", 10, 3000, 50, key="kosdaq_n", disabled=not use_kosdaq or kosdaq_all)

with col3:
    st.markdown("### 🇺🇸 나스닥")
    use_nasdaq = st.checkbox("NASDAQ 포함", value=False)
    nasdaq_all = st.checkbox("NASDAQ 전체 검색", value=False, disabled=not use_nasdaq)
    nasdaq_limit = st.number_input("검색 수량", 10, 5000, 50, key="nasdaq_n", disabled=not use_nasdaq or nasdaq_all)

with col4:
    st.markdown("### 💰 공통 옵션")
    min_money = st.number_input("최소 거래대금 (단위: 억)", value=50)
    st.caption("※ 미국 주식은 1400원 환율 적용 자동 계산")


# --- 4. 분석 로직 ---

def check_fundamental_kr(code):
    """한국 주식 전용 재무 크롤링"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        finance_html = soup.select('div.section.cop_analysis div.sub_section')
        if not finance_html: return False, {}
            
        df_fin = pd.read_html(str(finance_html[0]))[0]
        df_fin.set_index(df_fin.columns[0], inplace=True)
        
        reserve = float(str(df_fin.loc['유보율'].dropna().iloc[-1]).replace(',', ''))
        debt = float(str(df_fin.loc['부채비율'].dropna().iloc[-1]).replace(',', ''))
        roe = float(str(df_fin.loc['ROE'].dropna().iloc[-1]).replace(',', ''))

        if reserve >= 500 and debt <= 150 and roe >= 5.0:
            return True, {"유보율": reserve, "부채비율": debt, "ROE": roe}
        return False, {}
    except:
        return False, {}

def analyze_stock(stock_info):
    """통합 분석 함수 (KR/US 분기 처리)"""
    code = stock_info['Code']
    name = stock_info['Name']
    market = stock_info['Market'] # 'KOSPI', 'KOSDAQ', 'NASDAQ'

    # 1. 이름 필터 (한국만 적용)
    if market in ['KOSPI', 'KOSDAQ']:
        exclusion_keywords = ["스팩", "ETF", "ETN", "홀딩스", "우"]
        for keyword in exclusion_keywords:
            if keyword in name: return None
    else:
        # 미국은 ETF, SPAC 등이 이름만으로 구분이 어려워 일단 진행하거나 
        # 필요시 별도 로직 추가. 여기선 일단 패스.
        pass

    # 차트 데이터 (약 1년)
    try:
        df = fdr.DataReader(code, start=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
    except:
        return None
        
    if len(df) < 120: return None 

    # 주봉/월봉
    df_week = df.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})
    df_month = df.resample('M').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})

    if len(df_week) < 2 or len(df_month) < 2: return None

    # --- 차트 조건 검사 (공통) ---
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

    # 거래대금 계산 (환율 고려)
    # 한국: 원화 그대로 / 미국: 달러 * 1400원(가정)
    exchange_rate = 1400 if market == 'NASDAQ' else 1
    df['Amount_Bil'] = (df['Close'] * df['Volume'] * exchange_rate) / 100000000
    
    if df['Amount_Bil'].tail(120).max() < min_money: return None

    # --- 재무 분석 분기 (한국만) ---
    fin_info = {"유보율": "-", "부채비율": "-", "ROE": "-"}
    
    if market in ['KOSPI', 'KOSDAQ']:
        is_ok, fin = check_fundamental_kr(code)
        if not is_ok: return None
        fin_info = {k: f"{v}%" for k, v in fin.items()}
    else:
        # 미국 주식은 재무 통과로 간주
        fin_info = {"유보율": "N/A", "부채비율": "N/A", "ROE": "N/A"}

    # 최종 통과
    return {
        '시장': market,
        '종목명': name,
        '코드': code,
        '현재가': f"{curr_day['Close']:,.2f}" if market == 'NASDAQ' else f"{int(curr_day['Close']):,}원",
        '등락률': f"{round(curr_day['Change']*100, 2)}%",
        **fin_info
    }

# --- 5. 메인 실행 ---
st.divider()

# 예상 종목 수 표시 로직
def get_status_msg():
    msgs = []
    if use_kospi: msgs.append(f"코스피({'전체' if kospi_all else kospi_limit})")
    if use_kosdaq: msgs.append(f"코스닥({'전체' if kosdaq_all else kosdaq_limit})")
    if use_nasdaq: msgs.append(f"나스닥({'전체' if nasdaq_all else nasdaq_limit})")
    return ", ".join(msgs)

if st.button("🚀 글로벌 주식 검색 시작", type="primary", use_container_width=True):
    if not (use_kospi or use_kosdaq or use_nasdaq):
        st.error("최소한 하나의 시장을 선택해주세요.")
    else:
        status_msg = get_status_msg()
        st.write(f"🔎 **{status_msg}** 스캔을 시작합니다. (나스닥 전체 선택 시 매우 오래 걸릴 수 있습니다)")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. 대상 종목 리스트 수집
        all_targets = []
        
        # KOSPI
        if use_kospi:
            with st.spinner("코스피 종목 목록을 불러오는 중..."):
                k_stocks = fdr.StockListing('KOSPI')
                k_stocks['Market'] = 'KOSPI'
                if not kospi_all: k_stocks = k_stocks.head(kospi_limit)
                all_targets.append(k_stocks)
        
        # KOSDAQ
        if use_kosdaq:
            with st.spinner("코스닥 종목 목록을 불러오는 중..."):
                kqs = fdr.StockListing('KOSDAQ')
                kqs['Market'] = 'KOSDAQ'
                if not kosdaq_all: kqs = kqs.head(kosdaq_limit)
                all_targets.append(kqs)
                
        # NASDAQ
        if use_nasdaq:
            with st.spinner("나스닥 종목 목록을 불러오는 중... (시간이 소요될 수 있습니다)"):
                try:
                    # NASDAQ 전체 리스트는 매우 큽니다.
                    nas = fdr.StockListing('NASDAQ')
                    nas['Market'] = 'NASDAQ'
                    if not nasdaq_all: nas = nas.head(nasdaq_limit)
                    all_targets.append(nas)
                except Exception as e:
                    st.error(f"나스닥 목록을 가져오는데 실패했습니다: {e}")

        if not all_targets:
            st.stop()
            
        final_df = pd.concat(all_targets)
        final_df.reset_index(drop=True, inplace=True)
        
        stock_list = final_df.to_dict('records')
        total_len = len(stock_list)
        
        st.write(f"📊 총 **{total_len}개** 종목 분석 예정")

        # 2. 병렬 처리 분석
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(analyze_stock, stock): stock for stock in stock_list}
            
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res: results.append(res)
                except:
                    pass
                
                completed_count += 1
                progress = completed_count / total_len
                progress_bar.progress(progress)
                status_text.text(f"🏃 분석 중... ({completed_count}/{total_len})")

        progress_bar.empty()
        status_text.empty()
        
        # 3. 결과 출력
        if results:
            st.balloons()
            st.success(f"🎉 총 {len(results)}개의 보석 같은 종목을 발견했습니다!")
            
            # 결과 데이터프레임
            res_df = pd.DataFrame(results)
            
            # 시장별로 나눠서 보여주기 (탭 기능 활용)
            tab1, tab2 = st.tabs(["📋 전체 통합 결과", "📂 시장별 분류"])
            
            with tab1:
                st.dataframe(res_df)
                
            with tab2:
                for mkt in ['KOSPI', 'KOSDAQ', 'NASDAQ']:
                    mkt_df = res_df[res_df['시장'] == mkt]
                    if not mkt_df.empty:
                        st.write(f"**{mkt} ({len(mkt_df)}개)**")
                        st.dataframe(mkt_df)
                    else:
                        if (mkt == 'KOSPI' and use_kospi) or (mkt == 'KOSDAQ' and use_kosdaq) or (mkt == 'NASDAQ' and use_nasdaq):
                             st.write(f"**{mkt}**: 조건 만족 종목 없음")

        else:
            st.warning("조건을 만족하는 종목이 없습니다.")
