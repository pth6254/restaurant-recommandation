"""
main.py
-------
애플리케이션 진입점 및 HITL 제어 로직.

변경사항:
- Ollama 연결 상태 사전 확인
- 사용 중인 로컬 모델 목록 출력
"""

import uuid
import os
import requests
from dotenv import load_dotenv

load_dotenv()


# ✅ LangSmith Tracing 설정
def setup_langsmith():
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = os.getenv(
            "LANGCHAIN_PROJECT", "restaurant-curator"
        )
        print(f"✅ LangSmith Tracing 활성화 | 프로젝트: {os.environ['LANGCHAIN_PROJECT']}")
    else:
        print("⚠️  LangSmith Tracing 비활성화 (LANGCHAIN_API_KEY 없음)")


# ✅ Ollama 연결 및 모델 보유 여부 확인
def check_ollama():
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    required_models = ["qwen3.5:9b", "exaone3.5:7.8b", "gemma4:latest"]

    print(f"\n🔌 Ollama 연결 확인 중... ({base_url})")
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        available = [m["name"] for m in resp.json().get("models", [])]

        all_ok = True
        for model in required_models:
            # 태그 없이 이름만 비교 (예: qwen3.5 포함 여부)
            found = any(model.split(":")[0] in a for a in available)
            status = "✅" if found else "❌"
            if not found:
                all_ok = False
            print(f"  {status} {model}")

        if not all_ok:
            print("\n⚠️  일부 모델이 없습니다. 아래 명령으로 설치하세요:")
            for m in required_models:
                print(f"     ollama pull {m}")
        else:
            print("  모든 모델 준비 완료 🎉")

    except requests.exceptions.ConnectionError:
        print("❌ Ollama에 연결할 수 없습니다.")
        print("   Ollama가 실행 중인지 확인하세요: ollama serve")
        raise SystemExit(1)
    except Exception as e:
        print(f"⚠️  Ollama 확인 중 오류: {e} (계속 진행)")


setup_langsmith()
check_ollama()

from graph import app


def run_restaurant_guest():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("\n=== 🍽️ AI 맛집 추천 시스템 가동 ===")
    print("   powered by Ollama (qwen3.5 / exaone3.5 / gemma4)")
    user_query = input("\n어떤 맛집을 찾으시나요? (예: 강남역 근처 분위기 좋은 일식집): ")

    # ── Phase 1: Manager → Filter ──
    print("\n[1/3] 맛집 검색 및 필터링 중...\n")
    for event in app.stream({"query": user_query}, config):
        for node_name, _ in event.items():
            node_labels = {
                "manager":  "📋 질문 분석       (qwen3.5:9b)",
                "searcher": "🔎 맛집 검색       (Tavily)",
                "filter":   "🧹 데이터 필터링   (qwen3.5:9b)",
            }
            label = node_labels.get(node_name, node_name)
            print(f"  ✔️  {label} 완료")

    # ── HITL ──
    current_state = app.get_state(config)
    candidates = current_state.values.get("filtered_candidates", [])

    if not candidates:
        print("\n❌ 조건에 맞는 맛집을 찾지 못했습니다.")
        return

    print("\n" + "=" * 50)
    print("🤖 AI가 찾은 후보지 리스트:")
    print("-" * 50)
    for i, c in enumerate(candidates):
        score = c.get("score", "N/A")
        price = c.get("price_range", "")
        price_str = f"  |  {price}" if price else ""
        print(f"  [{i}] {c['name']}  (평점: {score}{price_str})")
    print("=" * 50)

    selection = input("\n👉 상세 분석할 식당 번호 입력 (여러 개는 쉼표로 구분): ")
    selected_indices = [int(x.strip()) for x in selection.split(",")]
    num_selected = len(selected_indices)

    app.update_state(config, {"selected_indices": selected_indices, "insights": []})

    # ── Phase 2: 병렬 Extract + 분석 ──
    print(f"\n[2/3] {num_selected}개 식당 병렬 크롤링 및 분석 중...\n")
    print("      Extractor: exaone3.5:7.8b  |  Analyst: exaone3.5:7.8b")
    print("      Collector: gemma4:latest\n")
    completed = 0
    for event in app.stream(None, config):
        for node_name, _ in event.items():
            if node_name == "restaurant_subgraph":
                completed += 1
                print(f"  ✔️  식당 분석 완료 ({completed}/{num_selected})")
            elif node_name == "collector":
                print("  ✔️  전체 결과 취합 완료  (gemma4:latest)")
            elif node_name == "writer":
                print("  ✔️  최종 리포트 작성 완료  (gemma4:latest)")

    # ── Phase 3: 결과 출력 ──
    print("\n[3/3] 분석 완료!\n")
    final_state = app.get_state(config)
    print("=" * 50)
    print(final_state.values.get("final_answer", "결과를 가져오지 못했습니다."))
    print("=" * 50)

    if os.getenv("LANGCHAIN_API_KEY"):
        project = os.environ.get("LANGCHAIN_PROJECT", "restaurant-curator")
        print(f"\n🔍 실행 추적 → https://smith.langchain.com/projects/{project}")


if __name__ == "__main__":
    run_restaurant_guest()