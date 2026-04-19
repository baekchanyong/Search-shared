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
    
    # [좌측] 채팅 입출력 관리
    prompt = st.chat_input("새로운 룰 아이디어를 입력하세요...")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

    with chat_col:
        st.subheader("💬 AI 게임 마스터와 대화")
        
        # 이전 메시지 렌더링
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # 새 메시지가 입력되었을 때만 답변 생성
        if prompt:
            with st.chat_message("assistant"):
                with st.spinner("규칙을 분석하고 답변을 준비 중입니다... 👀"):
                    response = st.write_stream(stream_chat_response(st.session_state.messages))
                st.session_state.messages.append({"role": "assistant", "content": response})

    # [우측] 실시간 룰 정리 현황판
    with status_col:
        st.subheader("📋 실시간 룰 정리 현황")
        
        # 새 메시지 입력 시 백그라운드 룰 추출 실행
        if prompt:
            with st.spinner("방금 대화를 바탕으로 현황판을 업데이트하고 있습니다..."):
                st.session_state.current_rule_status = extract_current_rules(st.session_state.messages)
        
        # 현황 출력
        if "current_rule_status" in st.session_state:
            st.info(st.session_state.current_rule_status)
        else:
            st.info("여기에 우리가 대화한 게임의 상태(참가자 수, 승계 조건 등)가 실시간으로 분석되어 표시됩니다.")
            
        # 첫 인사 외에 사용자/마스터의 대화가 진행되었을 때만 룰 조율 완료 버튼 노출
        if len(st.session_state.messages) > 2:
            st.divider()
            
            # 여기서 st.button을 바로 렌더링하면 prompt 로직 하위라서 뷰가 약간 불안정할 수 있음
            # 클릭 이벤트 처리
            if st.button("📝 현재 룰 조율 완료 및 시뮬레이터로 전송", type="primary", use_container_width=True):
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
    
    # 화면 강제 갱신으로 스크롤 및 상태 정리
    if prompt:
        st.rerun()
