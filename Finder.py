import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="주식 검색기", layout="wide")

st.title("📈 주식 검색기")

# --- 2. 공지사항 ---
with st.expander("📢 공지사항", expanded=False):
    st.write("공지사항 내용")

st.divider()

# --- 3. 검색 조건 설정 (체크박스 도입) ---
st.subheader("🛠 검색 조건 설정 (원하는 조건만 체크하세요)")

# 조건을 그룹별로 나누어 배치 (가독성 향상)
tab1, tab2, tab3 = st.tabs(["📊 차트/캔들 조건", "📈 이동평균선 조건", "💰 재무/기타 조건"])

with tab1:
    st.markdown("##### 캔들 및 패턴")
    c2 = st.checkbox("2. (월봉) 현재 캔들이 양봉(+)", value=True)
    c3 = st.checkbox("3. (주봉) 고가가 직전 봉보다 높음", value=True)
    c4 = st.checkbox("4. (주봉) 저가가 직전 봉보다 높음", value=True)

with tab2:
    col_ma1, col_ma2 = st.columns(2)
    with col_ma1:
        st.markdown("##### 이평선 배열 (정배열 등)")
        c5 = st.checkbox("5. (일봉) 60이평 <= 120이평", value=True)
        c6 = st.checkbox("6. (일봉) 20이평 <= 60이평", value=True)
        c7 = st.checkbox("7. (일봉) 5이평 >= 10이평", value=True)
        c8 = st.checkbox("8. (일봉) 10이평 >= 20이평", value=True)
    with col_ma2:
        st.markdown("##### 이평선 방향 (추세)")
        c9 = st.checkbox("9. (일봉) 5이평 상승 또는 보합", value=True)
        c10 = st.checkbox("10. (일봉) 10이평 상승", value=True)
        c11 = st.checkbox("11. (일봉) 20이평 상승", value=True)

with tab3:
    st.markdown("##### 재무 및 기타 (한국 주식만 적용)")
    c1 = st.checkbox("1. 제외 종목 필터 (관리/스팩/ETF 등)", value=True)
    c12 = st.checkbox("12. 거래대금 조건 적용", value=True)
    min_money = st.number_input("   └ 최소 거래대금 (단위: 억)", value=50, disabled=not c12)
    
    st.markdown("---")
    st.caption("※ 아래 재무 조건은 한국장(KOSPI, KOSDAQ)에만 적용됩니다.")
    c13 = st.checkbox("13. 유보율 500% 이상", value=True)
    c14 = st.checkbox("14. 부채비율 150% 이하", value=True)
    c15 = st.checkbox("15. 최근 분기 ROE 5% 이상", value=True)

st.divider()

# --- 4. 시장 및 수량 설정 ---
st.subheader("🌍 시장 선택 및 분석 범위")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    st.markdown("### 🇰🇷 코스피")
    use_kospi = st.checkbox("KOSPI 포함", value=True)
    kospi_all = st.checkbox("KOSPI 전체 검색", value=False, disabled=not use_kospi)
    kospi_limit = st.number_input("검색 수량", 10, 3000, 50, key="k_limit", disabled=not use_kospi or kospi_all)

with col_m2:
    st.markdown("### 🇰🇷 코스닥")
    use_kosdaq = st.checkbox("KOSDAQ 포함", value=False)
    kosdaq_all = st.checkbox("KOSDAQ 전체 검색", value=False, disabled=not use_kosdaq)
    kosdaq_limit = st.number_input("검색 수량", 10, 3000, 50, key="kq_limit", disabled=not use_kosdaq or kosdaq_all)

with col_m3:
    st.markdown("### 🇺🇸 나스닥")
    use_nasdaq = st.checkbox("NASDAQ 포함", value=False)
    nasdaq_all = st.checkbox("NASDAQ 전체 검색", value=False, disabled=not use_nasdaq)
    nasdaq_limit = st.number_input("검색 수량", 10, 5000, 50, key="n_limit", disabled=not use_nasdaq or nasdaq_all)

# --- 5. 분석 로직 ---

def check_fundamental_kr(code):
    """한국 주식 재무 크롤링"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        finance_html = soup.select('div.section.cop_analysis div.sub_section')
        if not finance_html: return False, {}
            
        df_fin = pd.read_html(str(finance_html[0]))[0]
        df_fin.set_index(df_fin.columns[0], inplace=True)
        
        # 값 추출 (데이터 없으면 에러 발생 -> except로 이동)
        reserve = float(str(df_fin.loc['유보율'].dropna().iloc[-1]).replace(',', ''))
        debt = float(str(df_fin.loc['부채비율'].dropna().iloc[-1]).replace(',', ''))
        roe = float(str(df_fin.loc['ROE'].dropna().iloc[-1]).replace(',', ''))

        # 조건 검증 (체크된 것만 확인)
        # 하나라도 체크되어 있고 조건을 만족하지 못하면 False 리턴
        if c13 and reserve < 500: return False, {}
        if c14 and debt > 150: return False, {}
        if c15 and roe < 5.0: return False, {}

        return True, {"유보율": reserve, "부채비율": debt, "ROE": roe}
    except:
        # 데이터가 없거나 에러인 경우, 재무 조건을 체크했다면 탈락시킴
        if c13 or c14 or c15:
            return False, {}
        return True, {"유보율": "-", "부채비율": "-", "ROE": "-"}

def analyze_stock(stock_info):
    code = stock_info['Code']
    name = stock_info['Name']
    market = stock_info['Market']

    # [조건 1] 제외 종목 필터 (체크되었고, 한국 시장일 때만)
    if c1 and market in ['KOSPI', 'KOSDAQ']:
        exclusion_keywords = ["스팩", "ETF", "ETN", "홀딩스", "우"]
        for keyword in exclusion_keywords:
            if keyword in name: return None

    # 데이터 가져오기
    try:
        df = fdr.DataReader(code, start=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
    except:
        return None
        
    if len(df) < 120: return None 

    # 주봉/월봉 생성
    df_week = df.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})
    df_month = df.resample('M').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})

    if len(df_week) < 2 or len(df_month) < 2: return None

    curr_day = df.iloc[-1]
    curr_week = df_week.iloc[-1]; prev_week = df_week.iloc[-2]
    curr_month = df_month.iloc[-1]; prev_month_close = df_month.iloc[-2]['Close']

    # --- 체크박스 조건 검증 ---
    
    # [조건 2] 월봉 양봉
    if c2 and (curr_month['Close'] <= prev_month_close): return None
    
    # [조건 3] 주봉 고가 갱신
    if c3 and (curr_week['High'] <= prev_week['High']): return None
    
    # [조건 4] 주봉 저가 상승
    if c4 and (curr_week['Low'] <= prev_week['Low']): return None

    # 이평선 계산
    ma5 = df['Close'].rolling(5).mean()
    ma10 = df['Close'].rolling(10).mean()
    ma20 = df['Close'].rolling(20).mean()
    ma60 = df['Close'].rolling(60).mean()
    ma120 = df['Close'].rolling(120).mean()
    
    if ma120.isnull().iloc[-1]: return None # 데이터 부족 시

    c_ma5 = ma5.iloc[-1]; p_ma5 = ma5.iloc[-2]
    c_ma10 = ma10.iloc[-1]; p_ma10 = ma10.iloc[-2]
    c_ma20 = ma20.iloc[-1]; p_ma20 = ma20.iloc[-2]
    c_ma60 = ma60.iloc[-1]
    c_ma120 = ma120.iloc[-1]

    # [조건 5~8] 이평선 정배열
    if c5 and not (c_ma60 <= c_ma120): return None
    if c6 and not (c_ma20 <= c_ma60): return None
    if c7 and not (c_ma5 >= c_ma10): return None
    if c8 and not (c_ma10 >= c_ma20): return None

    # [조건 9~11] 이평선 상승
    if c9 and not (c_ma5 >= p_ma5): return None
    if c10 and not (c_ma10 > p_ma10): return None
    if c11 and not (c_ma20 > p_ma20): return None

    # [조건 12] 거래대금
    if c12:
        exchange_rate = 1400 if market == 'NASDAQ' else 1
        df['Amount_Bil'] = (df['Close'] * df['Volume'] * exchange_rate) / 100000000
        if df['Amount_Bil'].tail(120).max() < min_money: return None

    # [조건 13~15] 재무 분석 (한국 주식만, 그리고 체크된 경우만)
    fin_info = {"유보율": "-", "부채비율": "-", "ROE": "-"}
    
    # 재무 조건 중 하나라도 체크되어 있다면 크롤링 시도
    need_fundamental_check = (c13 or c14 or c15) and (market in ['KOSPI', 'KOSDAQ'])
    
    if need_fundamental_check:
        is_ok, fin = check_fundamental_kr(code)
        if not is_ok: return None
        fin_info = {k: f"{v}%" for k, v in fin.items()}
    elif market == 'NASDAQ':
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

# --- 6. 실행 버튼 ---
st.divider()

def get_target_msg():
    msgs = []
    if use_kospi: msgs.append(f"코스피({'전체' if kospi_all else kospi_limit})")
    if use_kosdaq: msgs.append(f"코스닥({'전체' if kosdaq_all else kosdaq_limit})")
    if use_nasdaq: msgs.append(f"나스닥({'전체' if nasdaq_all else nasdaq_limit})")
    return ", ".join(msgs)

if st.button("분석시작", type="primary", use_container_width=True):
    if not (use_kospi or use_kosdaq or use_nasdaq):
        st.error("시장을 하나 이상 선택해주세요.")
    else:
        st.write(f"🔎 **{get_target_msg()}** 분석을 시작합니다... (선택된 조건만 검사)")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 종목 리스트 수집
        all_targets = []
        try:
            if use_kospi:
                k = fdr.StockListing('KOSPI'); k['Market'] = 'KOSPI'
                if not kospi_all: k = k.head(kospi_limit)
                all_targets.append(k)
            if use_kosdaq:
                kq = fdr.StockListing('KOSDAQ'); kq['Market'] = 'KOSDAQ'
                if not kosdaq_all: kq = kq.head(kosdaq_limit)
                all_targets.append(kq)
            if use_nasdaq:
                ns = fdr.StockListing('NASDAQ'); ns['Market'] = 'NASDAQ'
                if not nasdaq_all: ns = ns.head(nasdaq_limit)
                all_targets.append(ns)
        except Exception as e:
            st.error(f"종목 리스트 확보 실패: {e}")
            st.stop()

        if not all_targets:
            st.warning("검색 대상 종목이 없습니다.")
            st.stop()

        final_df = pd.concat(all_targets).reset_index(drop=True)
        stock_list = final_df.to_dict('records')
        total_len = len(stock_list)

        results = []
        # 병렬 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(analyze_stock, stock): stock for stock in stock_list}
            
            cnt = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res: results.append(res)
                except: pass
                
                cnt += 1
                progress_bar.progress(cnt / total_len)
                status_text.text(f"🏃 {cnt}/{total_len} 종목 분석 중...")

        progress_bar.empty()
        status_text.empty()

        if results:
            st.success(f"🎉 조건에 맞는 {len(results)}개 종목 발견!")
            res_df = pd.DataFrame(results)
            
            tab_res1, tab_res2 = st.tabs(["📋 전체 결과", "📂 시장별 분류"])
            with tab_res1: st.dataframe(res_df)
            with tab_res2:
                for mkt in ['KOSPI', 'KOSDAQ', 'NASDAQ']:
                    sub = res_df[res_df['시장'] == mkt]
                    if not sub.empty:
                        st.write(f"**{mkt} ({len(sub)}개)**")
                        st.dataframe(sub)
        else:
            st.warning("조건을 만족하는 종목이 하나도 없습니다. 조건을 조금 더 풀어보세요.")
