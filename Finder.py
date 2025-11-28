
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
    st.write("TEST 중입니다")

st.divider()

# --- 3. 검색 조건 설정 ---
st.subheader("🛠 검색 조건 설정")

tab1, tab2, tab3 = st.tabs(["📊 차트/캔들", "📈 이동평균선", "💰 재무/기타"])

# [Tab 1] 캔들/패턴
with tab1:
    all_c_group1 = st.checkbox("전체선택/해제", value=True, key="g1")
    
    c2 = st.checkbox("2. (월봉) 이번 달 캔들이 양봉(+) 상태인가?", value=all_c_group1)
    c3 = st.checkbox("3. (주봉) 이번 주 고가가 지난주 고가보다 높은가?", value=all_c_group1)
    c4 = st.checkbox("4. (주봉) 이번 주 저가가 지난주 저가보다 높은가?", value=all_c_group1)

# [Tab 2] 이동평균선
with tab2:
    all_c_group2 = st.checkbox("전체선택/해제", value=True, key="g2")

    col_ma1, col_ma2 = st.columns(2)
    with col_ma1:
        c5 = st.checkbox("5. (일봉) 60일선이 120일선보다 아래에 있는가? (장기 역배열)", value=all_c_group2)
        c6 = st.checkbox("6. (일봉) 20일선이 60일선보다 아래에 있는가?", value=all_c_group2)
        c7 = st.checkbox("7. (일봉) 5일선이 10일선 위에 있는가? (단기 정배열)", value=all_c_group2)
        c8 = st.checkbox("8. (일봉) 10일선이 20일선 위에 있는가?", value=all_c_group2)
    with col_ma2:
        c9 = st.checkbox("9. (일봉) 5일선이 상승 중이거나 평평한가?", value=all_c_group2)
        c10 = st.checkbox("10. (일봉) 10일선이 상승 중인가?", value=all_c_group2)
        c11 = st.checkbox("11. (일봉) 20일선이 상승 중인가?", value=all_c_group2)

# [Tab 3] 재무/기타
with tab3:
    all_c_group3 = st.checkbox("전체선택/해제", value=True, key="g3")

    st.markdown("종목 필터 및 수급")
    c1 = st.checkbox("1. 위험 종목 제외 (관리/환기/스팩/ETF/ETN/초저유동성 등)", value=all_c_group3)
    c12 = st.checkbox("12. (일봉) 최근 120봉 이내에 '설정된 금액' 이상 거래대금이 1회 이상 발생했는가?", value=all_c_group3)
    min_money = st.number_input("   └ 기준 거래대금 (단위: 억)", value=50, disabled=not c12)
    
    st.markdown("재무 건전성 (한국 주식 전용)")
    st.caption("※ 나스닥은 재무 데이터 수집 제한으로 자동 통과됩니다.")
    c13 = st.checkbox("13. 유보율 500% 이상", value=all_c_group3)
    c14 = st.checkbox("14. 부채비율 150% 이하", value=all_c_group3)
    c15 = st.checkbox("15. 최근 분기 ROE 5% 이상", value=all_c_group3)

st.divider()

# --- 4. 시장 및 수량 설정 ---
st.subheader("분석시장 선택")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    st.markdown("### 🇰🇷 KOSPI")
    use_kospi = st.checkbox("🇰🇷 KOSPI", value=True)
    kospi_all = st.checkbox("KOSPI 전체 검색", value=False, disabled=not use_kospi)
    kospi_limit = st.number_input("검색 수량", 10, 3000, 50, key="k_limit", disabled=not use_kospi or kospi_all)

with col_m2:
    st.markdown("### 🇰🇷 KOSDAQ")
    use_kosdaq = st.checkbox("🇰🇷 KOSDAQ", value=False)
    kosdaq_all = st.checkbox("KOSDAQ 전체 검색", value=False, disabled=not use_kosdaq)
    kosdaq_limit = st.number_input("검색 수량", 10, 3000, 50, key="kq_limit", disabled=not use_kosdaq or kosdaq_all)

with col_m3:
    st.markdown("### 🇺🇸 NASDAQ")
    use_nasdaq = st.checkbox("🇺🇸 NASDAQ", value=False)
    nasdaq_all = st.checkbox("NASDAQ 전체 검색", value=False, disabled=not use_nasdaq)
    nasdaq_limit = st.number_input("검색 수량", 10, 5000, 50, key="n_limit", disabled=not use_nasdaq or nasdaq_all)

# --- 5. ---

def check_fundamental_kr(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        finance_html = soup.select('div.section.cop_analysis div.sub_section')
        if not finance_html: return Fal, {}
            
        df_fin = pd.read_html(str(finance_html[0]))[0]
        df_fin.set_index(df_fin.columns[0], inplace=True)
        
        reserve = float(str(df_fin.loc['유보율'].dropna().iloc[-1]).replace(',', ''))
        debt = float(str(df_fin.loc['부채비율'].dropna().iloc[-1]).replace(',', ''))
        roe = float(str(df_fin.loc['ROE'].dropna().iloc[-1]).replace(',', ''))

        if c13 and reserve < 500: return False, {}
        if c14 and debt > 150: return False, {}
        if c15 and roe < 5.0: return False, {}

        return True, {"유보율": reserve, "부채비율": debt, "ROE": roe}
    except:
        if c13 or c14 or c15: return False, {}
        return True, {"유보율": "-", "부채비율": "-", "ROE": "-"}

def analyze_stock(stock_info):
    code = stock_info['Code']
    name = stock_info['Name']
    market = stock_info['Market']
    actual_rank = stock_info['Actual_Rank'] # 실제 시총 순위 받아오기
    marcap = stock_info.get('Marcap', 0)

    # [조건 1] 제외 종목 필터
    if c1 and market in ['KOSPI', 'KOSDAQ']:
        exclusion_keywords = ["스팩", "ETF", "ETN", "홀딩스", "우"]
        for keyword in exclusion_keywords:
            if keyword in name: return None

    try:
        df = fdr.DataReader(code, start=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
    except:
        return None
        
    if len(df) < 120: return None 

    df_week = df.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})
    df_month = df.resample('M').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})

    if len(df_week) < 2 or len(df_month) < 2: return None

    curr_day = df.iloc[-1]
    curr_week = df_week.iloc[-1]; prev_week = df_week.iloc[-2]
    curr_month = df_month.iloc[-1]; prev_month_close = df_month.iloc[-2]['Close']

    # 캔들 조건
    if c2 and (curr_month['Close'] <= prev_month_close): return None
    if c3 and (curr_week['High'] <= prev_week['High']): return None
    if c4 and (curr_week['Low'] <= prev_week['Low']): return None

    # 이평선 계산
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

    # 이평선 조건
    if c5 and not (c_ma60 <= c_ma120): return None
    if c6 and not (c_ma20 <= c_ma60): return None
    if c7 and not (c_ma5 >= c_ma10): return None
    if c8 and not (c_ma10 >= c_ma20): return None
    if c9 and not (c_ma5 >= p_ma5): return None
    if c10 and not (c_ma10 > p_ma10): return None
    if c11 and not (c_ma20 > p_ma20): return None

    # 거래대금 조건
    if c12:
        exchange_rate = 1400 if market == 'NASDAQ' else 1
        df['Amount_Bil'] = (df['Close'] * df['Volume'] * exchange_rate) / 100000000
        if df['Amount_Bil'].tail(120).max() < min_money: return None

    # 재무 분석
    fin_info = {"유보율": "-", "부채비율": "-", "ROE": "-"}
    need_fundamental_check = (c13 or c14 or c15) and (market in ['KOSPI', 'KOSDAQ'])
    
    if need_fundamental_check:
        is_ok, fin = check_fundamental_kr(code)
        if not is_ok: return None
        fin_info = {k: f"{v}%" for k, v in fin.items()}
    elif market == 'NASDAQ':
         fin_info = {"유보율": "N/A", "부채비율": "N/A", "ROE": "N/A"}

    return {
        '순위': actual_rank, # 실제 시총 순위 (화면 표시용)
        '시장': market,
        '종목명': name,
        '코드': code,
        '현재가': f"{curr_day['Close']:,.2f}" if market == 'NASDAQ' else f"{int(curr_day['Close']):,}원",
        '등락률': f"{round(curr_day['Change']*100, 2)}%",
        '시가총액': f"{int(marcap / 100000000):,}억" if market != 'NASDAQ' else "정보없음",
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
        
        all_targets = []
        try:
            # 1. 데이터를 먼저 다 가져와서 '시총 순위'를 매깁니다.
            if use_kospi:
                k = fdr.StockListing('KOSPI'); k['Market'] = 'KOSPI'
                # Marcap이 없는 경우 대비 0 처리
                if 'Marcap' not in k.columns: k['Marcap'] = 0
                
                # 전체를 가져와서 정렬 후 순위 매김
                k = k.sort_values(by='Marcap', ascending=False)
                k['Actual_Rank'] = range(1, len(k) + 1) # 실제 순위 부여
                
                if not kospi_all: k = k.head(kospi_limit) # 그 다음 자르기
                all_targets.append(k)
                
            if use_kosdaq:
                kq = fdr.StockListing('KOSDAQ'); kq['Market'] = 'KOSDAQ'
                if 'Marcap' not in kq.columns: kq['Marcap'] = 0
                
                kq = kq.sort_values(by='Marcap', ascending=False)
                kq['Actual_Rank'] = range(1, len(kq) + 1)
                
                if not kosdaq_all: kq = kq.head(kosdaq_limit)
                all_targets.append(kq)
                
            if use_nasdaq:
                ns = fdr.StockListing('NASDAQ'); ns['Market'] = 'NASDAQ'
                # 나스닥은 FDR 데이터에 시총이 보통 없음 (0으로 처리 후 임시 순위 부여)
                if 'Marcap' not in ns.columns: ns['Marcap'] = 0
                ns['Actual_Rank'] = range(1, len(ns) + 1) # 목록 순서대로 (나스닥은 알파벳순일수 있음)
                
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
            
            # 결과 표시 (이미 실제 순위가 '순위' 컬럼에 들어있음)
            res_df = pd.DataFrame(results)
            
            # 보기 좋게 정렬 (순위 오름차순: 1등부터 보이게)
            # 만약 코스피, 코스닥을 섞어서 본다면 각각의 순위가 섞여서 보일 것입니다.
            res_df = res_df.sort_values(by=['시장', '순위'])
            
            tab_res1, tab_res2 = st.tabs(["📋 전체 결과", "📂 시장별 분류"])
            with tab_res1: st.dataframe(res_df, hide_index=True)
            with tab_res2:
                for mkt in ['KOSPI', 'KOSDAQ', 'NASDAQ']:
                    sub = res_df[res_df['시장'] == mkt]
                    if not sub.empty:
                        st.write(f"**{mkt} ({len(sub)}개)**")
                        st.dataframe(sub, hide_index=True)
        else:
            st.warning("조건을 만족하는 종목이 하나도 없습니다. 조건을 조금 더 풀어보세요.")
