import streamlit as st
from dotenv import load_dotenv
import os

# 모듈 임포트 (추후 생성할 파일들)
from ui.rule_chat import render_rule_builder
from ui.simulation_dashboard import render_simulation_dashboard

# 환경 변수 로드
load_dotenv()

st.set_page_config(
    page_title="AI Game Tester MVP",
    page_icon="🎲",
    layout="wide"
)

def main():
    st.sidebar.title("⚙️ 설정")
    engine_choice = st.sidebar.radio(
        "시뮬레이션 엔진 선택",
        ["LLM 기반 (소셜/대화형 게임)", "수학적 강화학습 (업데이트 예정)"]
    )
    
    tab1, tab2 = st.tabs(["💬 게임 규칙 빌더", "📊 시뮬레이션 및 분석"])
    
    with tab1:
        st.header("게임 규칙 설계 (Rule Builder)")
        st.caption("AI를 통해 게임의 제목, 참가자 수, 직업, 승리 조건을 정리하세요.")
        render_rule_builder()
        
    with tab2:
        st.header("시뮬레이션 결과 및 밸런스 검증")
        if engine_choice == "LLM 기반 (소셜/대화형 게임)":
            render_simulation_dashboard()
        else:
            st.info("수학적 시뮬레이션 엔진은 현재 준비 중입니다.")

if __name__ == "__main__":
    main()
