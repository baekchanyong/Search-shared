import streamlit as st
from core.llm_engine import get_chat_response, stream_chat_response, stream_generate_content, extract_current_rules

def render_rule_builder():
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.messages.append({
            "role": "assistant", 
            "content": "안녕하세요! 저는 게임 디자인 마스터입니다. 어떤 종류의 게임(예: 마피아, 먹이사슬 등)을 만드려고 하시나요? 참가 인원수와 대략적인 아이디어를 먼저 말씀해 주시면 체계적으로 룰을 세팅해 드릴게요."
        })
        
    chat_col, status_col = st.columns([5, 3])
    
    # [하단] 채팅 입력 관리 (동작은 하단에 고정되지만 먼저 선언)
    prompt = st.chat_input("새로운 룰 아이디어를 입력하세요...")
    
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

    # ==========================
    # 1) UI 선 그리기 (좌측 / 우측)
    # ==========================
    
    # [좌측] 채팅 이전 내역 렌더링
    with chat_col:
        st.subheader("💬 AI 게임 마스터와 대화")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # 새로운 응답이 들어갈 자리를 미리 예약
        assistant_placeholder = st.empty()

    # [우측] 실시간 룰 정리 현황 정적 렌더링
    with status_col:
        st.subheader("📋 실시간 룰 정리 현황")
        status_placeholder = st.empty()
        
        if "current_rule_status" in st.session_state:
            status_placeholder.info(st.session_state.current_rule_status)
        else:
            status_placeholder.info("여기에 우리가 대화한 게임의 상태(참가자 수, 승계 조건 등)가 실시간으로 분석되어 표시됩니다.")
            
        # 첫 인사 외에 대화가 진행되었을 때만 완료 버튼 노출
        btn_placeholder = st.empty()
        finalize_clicked = False
        if len(st.session_state.messages) > 2:
            st.divider()
            finalize_clicked = btn_placeholder.button("📝 현재 룰 조율 완료 및 시뮬레이터로 전송", type="primary", use_container_width=True)

    # ==========================
    # 2) 이벤트 발생 시 시간이 걸리는 API 호출 진행
    # ==========================
    
    if prompt:
        # 1. 채팅창(좌측) 답변 생성 및 스트리밍 노출
        with assistant_placeholder.chat_message("assistant"):
            with st.spinner("규칙을 분석하고 답변을 준비 중입니다... 👀"):
                response = st.write_stream(stream_chat_response(st.session_state.messages))
            st.session_state.messages.append({"role": "assistant", "content": response})

        # 2. 상태창(우측) 요약 생성
        # (현황판에 업데이트 중임을 알리는 상태 표시)
        status_placeholder.info("🔄 방금 대화를 바탕으로 현황판을 업데이트하고 있습니다...")
        
        # 모델 요약 함수 호출 (이 동안 스트림은 아니지만 우측 UI가 이미 존재하므로 멈춰있는 느낌 해소)
        new_status = extract_current_rules(st.session_state.messages)
        st.session_state.current_rule_status = new_status
        
        # 결과 반영
        status_placeholder.info(new_status)
        
        # 깔끔하게 UI를 정리하기 위해 화면 갱신
        st.rerun()

    # ==========================
    # 3) 룰 조율 완료 버튼 동작
    # ==========================
    if finalize_clicked:
        with status_col:
            st.info("🔄 진행 알림: 흩어진 대화를 모아 최종 '공식 룰북'으로 정리하여 작성 중입니다. (10초~30초 소요)")
            with st.container(border=True):
                summary_prompt = "지금까지 우리가 대화한 내용을 바탕으로, 이 게임의 전체 규칙(제목, 인원수, 직업과 능력, 낮과 밤 등 턴 진행 방식, 최종 승리 조건)을 완전무결한 '공식 룰북 매뉴얼' 형태로 출력해줘. 시뮬레이션 AI가 이 룰북만 보고 게임을 빈틈없이 진행할 수 있어야 해."
                
                temp_context = st.session_state.messages.copy()
                temp_context.append({"role": "user", "content": summary_prompt})
                
                final_rules = st.write_stream(stream_chat_response(temp_context))
                
                # 최종 룰을 세션에 저장
                st.session_state.final_rules = final_rules
                st.session_state.messages.append({"role": "user", "content": "여기까지의 룰을 확정해줘."})
                st.session_state.messages.append({"role": "assistant", "content": "완성된 게임 룰북은 다음과 같습니다:\n\n" + final_rules})
                
            st.success("✅ 규칙이 성공적으로 확정되었습니다! 상단의 [📊 시뮬레이션 및 분석] 탭으로 이동하세요.")

