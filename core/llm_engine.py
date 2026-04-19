import os
import google.generativeai as genai
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Streamlit Cloud의 Secrets 환경에서 API 키를 가져오기 위한 안전 장치
if not API_KEY:
    try:
        import streamlit as st
        API_KEY = st.secrets.get("GEMINI_API_KEY", None)
    except Exception:
        pass

if API_KEY:
    genai.configure(api_key=API_KEY)
    
    try:
        # 가용한 모델 중 가장 최신 버전의 flash 모델을 자동 선택 (하드코딩으로 인한 404 에러 방지)
        available_models = [m.name for m in genai.list_models() if 'flash' in m.name and 'generateContent' in m.supported_generation_methods]
        MODEL_NAME = available_models[-1] if available_models else "models/gemini-flash" # 가장 최신 버전 혹은 기본 별칭 사용
    except Exception:
        MODEL_NAME = "models/gemini-flash"
else:
    print("경고: GEMINI_API_KEY가 설정되지 않았습니다.")
    MODEL_NAME = "models/gemini-flash"

# 모델 설정
model = genai.GenerativeModel(MODEL_NAME)

SYSTEM_PROMPT = """너는 아주 뛰어나고 창의적인 보드게임 및 MT 게임 디자인 마스터 전문가야. 
초보 사용자가 게임에 대한 대략적인 아이디어를 주면, 너가 리드해서 게임의 제목, 참가자 수, 
각 역할(직업)의 능력과 비중, 승패 조건, 밤/낮 턴 구조 같은 세부 규칙들을 구체적이고 체계적이고 
빈틈없이 완성할 수 있게 질문하고 다듬어줘야 해.
질문은 한 번에 하나씩 하거나 선택지를 줘서 쉽게 대답할 수 있게 해. 
마피아 게임, 더 지니어스 게임(먹이사슬 등) 등 다양한 심리전 게임의 구조를 잘 이해하고 있어야 해."""

def get_chat_response(messages_history):
    """ Streamlit의 session_state.messages 구조를 받아서 Gemini 응답 생성 """
    try:
        # 새로운 제미나이 규격에 맞게 시스템 명령을 별도 모델로 선언하거나, 히스토리를 강제로 번갈아가게 만듦
        system_instruction = {"role": "user", "parts": [SYSTEM_PROMPT + "\n\n이제 이 페르소나에 맞춰 대답해."]}
        history_to_pass = [system_instruction, {"role": "model", "parts": ["네, 게임 기획 마스터로서 최선을 다하겠습니다."]}]
        
        for msg in messages_history[:-1]: # 마지막 질문(user)은 제외하고 히스토리에 담음
            role = "user" if msg["role"] == "user" else "model"
            # 이전 역할과 같다면 파트만 병합 (연속된 역할 에러 방지)
            if history_to_pass[-1]["role"] == role:
                history_to_pass[-1]["parts"].append(msg["content"])
            else:
                history_to_pass.append({"role": role, "parts": [msg["content"]]})
        
        chat = model.start_chat(history=history_to_pass)
        last_message = messages_history[-1]["content"] if messages_history else "대화를 시작합니다."
        response = chat.send_message(last_message)
        return response.text
    except Exception as e:
        return f"API 호출 에러: {str(e)}"

def stream_chat_response(messages_history):
    """ Streamlit 실시간 타이핑 효과를 위한 Generator 함수 """
    if not API_KEY:
        yield "\n[서버 에러: GEMINI_API_KEY가 정상적으로 로드되지 않았습니다. Streamlit Secrets 설정에 키가 제대로 입력되었는지 확인 후 앱을 재부팅(Reboot) 해주세요.]"
        return
        
    try:
        system_instruction = {"role": "user", "parts": [SYSTEM_PROMPT + "\n\n이제 이 페르소나에 맞춰 대답해."]}
        history_to_pass = [system_instruction, {"role": "model", "parts": ["네, 알겠습니다. 게임 마스터로서 최선을 다하겠습니다."]}]
        
        for msg in messages_history[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            if history_to_pass[-1]["role"] == role:
                history_to_pass[-1]["parts"].append(msg["content"])
            else:
                history_to_pass.append({"role": role, "parts": [msg["content"]]})
                
        chat = model.start_chat(history=history_to_pass)
        last_message = messages_history[-1]["content"] if messages_history else "대화를 시작해줘."
        
        response = chat.send_message(last_message, stream=True)
        # stream 응답 처리
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        yield f"\n[서버 통신 오류가 발생했습니다. 잠시 후 룰 조율을 다시 시도해주세요]\n상세 에러: {str(e)}"

def stream_generate_content(prompt):
    """ 규칙 요약 등 단발성 메시지의 실시간 스트리밍을 위한 Generator """
    try:
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        yield f"\n[서버 통신 오류가 발생했습니다. 잠시 후 시도해주세요]\n상세 에러: {str(e)}"

def extract_current_rules(messages_history):
    """현재까지의 대화를 바탕으로 실시간 룰 현황 요약 작성"""
    if not API_KEY:
        return "[오류: API 키 설정 안 됨]"
        
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages_history[-10:]]) # 최근 10개 대화만
    prompt = f"""
    아래는 사용자와 게임 마스터 간의 게임 룰 설계 대화입니다:
    {history_text}
    
    이 대화를 바탕으로 지금까지 확정되었거나 논의 중인 게임 룰을 추출해 아래 항목별로 마크다운을 써서 간략히 요약하세요.
    아직 논의되지 않은 항목은 '미정'이라고 표시하세요. 절대 임의로 상상해서 채우지 마세요.
    - **플레이어 수**: 
    - **직업 및 역할**: 
    - **게임 진행 순서/흐름**: 
    - **승리 조건**: 
    - **기타 특수 룰**: 
    """
    try:
        # 단발성 호출. API 지연 등의 무한 대기(Hanging) 방지를 위해 타임아웃/예외처리
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"현재 대화를 요약하는 중 오류가 발생했습니다: {str(e)}"

def stream_simulation_match(rules_text):
    """실시간 스트리밍으로 1회의 게임 시뮬레이션을 작동시키고 결과를 반환"""
    sim_prompt = f"""
너는 뛰어난 보드게임 플레이 인공지능이자 환경 시뮬레이터야.
주어진 규칙을 완벽하고 엄격하게 지켜서 처음부터 끝까지 1판의 게임을 가상으로 시뮬레이션 해.
게임 참가자 플레이어들은 서로를 이기기 위해 각자의 역할에서 최선의 전략적 판단과 논리적 추론, 심리전(거짓말)을 사용해.

가상 플레이어들(가령 플레이어 1~5)이 진행하는 대화와 턴(낮/밤 등)을 생동감있게 요약해서 서술해줘.
절대 룰에 없는 임의적인 요소를 추가하면 안 되며, 누군가의 승리/패배 조건이 만족되면 즉시 게임을 종료해.

[게임 규칙]
{rules_text}

***매우 중요***
시뮬레이션이 끝난 후, 출력의 제일 마지막에 반드시 아래와 같은 포맷으로 결과를 요약해. 프로그램이 파싱할 거니까 양식을 꼭 지켜:
===결과 요약===
승리팀: [예: 시민팀 또는 마피아팀 등]
생존역할: [예: 의사, 시민, 마피아 등]
주요승인: [문장으로 짧게 요약]
"""
    try:
        response = model.generate_content(sim_prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        yield f"===결과 요약===\n승리팀: 에러발생\n생존역할: 없음\n주요승인: {str(e)}"

def stream_analyze_simulation_results(rules_text, simulation_logs):
    """여러 판 진행된 시뮬레이션 로그를 바탕으로 실시간 스트리밍 분석"""
    analyze_prompt = f"""
너는 천재적인 보드게임 밸런스 기획자야.
아래는 사용자가 만든 게임의 [규칙]과, 이 규칙대로 AI들이 여러번 테스트플레이한 [종합 결과 로그]야.

[게임 규칙]
{rules_text}

[시뮬레이션 종합 결과 로그]
{simulation_logs}

로그를 유심히 분석하여 다음 정보들을 깔끔한 마크다운 양식으로 보고해줘:
1. 롤별 승률 분석 및 전체적인 게임 밸런스 평가
2. 필승법(Abuse) 가능성이 존재하는지 논리적 분석
3. 게임을 더 구조적이고 재미있게(혹은 밸런스 있게) 바꾸기 위한 추천 룰 개선안
"""
    try:
        response = model.generate_content(analyze_prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        yield f"분석 중 에러가 발생했습니다: {str(e)}"
