import uuid
from dotenv import load_dotenv
from graph import app  # 설계도 파일에서 컴파일된 app 임포트
from agents.agents import *

# 환경 변수 로드 (API 키 등)
load_dotenv()

def run_restaurant_guest():
    # 1. 세션 설정 (체크포인트를 구분하기 위한 고유 ID)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print("=== 🍽️ AI 맛집 추천 시스템 가동 ===")
    user_query = input("어떤 맛집을 찾으시나요? (예: 강남역 근처 분위기 좋은 일식집): ")
    
    # 2. 초기 실행 (Manager -> Router -> Searcher -> Filter -> Human_Approval 직전까지)
    print("\n[시스템] 분석을 시작합니다...")
    initial_state = {"query": user_query}
    
    # stream 모드로 실행하여 각 노드의 진행 상황을 출력
    for event in app.stream(initial_state, config):
        for node_name, state_update in event.items():
            print(f"✔️ {node_name} 단계 완료")

    # 3. [HITL] 중단점 확인 및 사용자 개입
    # Filter까지 끝나고 human_approval 노드 직전에서 멈춘 상태입니다.
    current_state = app.get_state(config)
    candidates = current_state.values.get("filtered_candidates", [])

    if not candidates:
        print("❌ 조건에 맞는 맛집을 찾지 못했습니다.")
        return

    print("\n" + "="*30)
    print("🤖 AI가 찾은 후보지 리스트입니다:")
    for i, candidate in enumerate(candidates):
        print(f"[{i}] {candidate['name']} (평점: {candidate.get('score', 'N/A')})")
    print("="*30)

    # 사용자로부터 분석할 식당 번호 입력받기
    selection = input("\n👉 상세 분석을 원하는 식당 번호를 입력하세요 (여러 개는 쉼표로 구분): ")
    selected_indices = [int(x.strip()) for x in selection.split(",")]

    # 4. 상태 업데이트 및 재개 (Resume)
    # 사용자가 선택한 번호를 State에 강제로 주입합니다.
    app.update_state(config, {"selected_indices": selected_indices})
    
    print("\n[시스템] 선택하신 식당의 리뷰를 심층 분석합니다...")
    
    # None을 입력으로 주면 멈췄던 지점부터 다시 시작합니다.
    for event in app.stream(None, config):
        for node_name, state_update in event.items():
            print(f"✔️ {node_name} 단계 완료")

    # 5. 최종 결과 출력
    final_state = app.get_state(config)
    print("\n✨ 최종 추천 리포트 ✨")
    print("-" * 40)
    print(final_state.values.get("final_answer"))
    print("-" * 40)

if __name__ == "__main__":
    run_restaurant_guest()