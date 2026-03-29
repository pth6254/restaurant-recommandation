from typing import TypedDict, List, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents import *


# 1. 상태(State) 정의
class AgentState(TypedDict):
    query: str
    location: str
    category: str
    preferences: List[str]
    max_price: Optional[int]
    candidates: List[dict]
    analysis_report: str
    final_answer: str
    retry_count: int

# 2. 노드 함수 선언 (내부 로직은 각 agent 파일에서 import 한다고 가정)
def manager(state: AgentState):
    print("---MANAGER: 계획 수립---")
    return {"query": state["query"], "retry_count": 0}

def router(state: AgentState) -> Literal["searcher", "analyst"]:
    print("---ROUTER: 경로 결정---")
    # 질문에 이미 구체적인 식당 이름이 있다면 바로 분석으로, 없다면 검색으로
    if any(word in state["query"] for word in ["추천", "찾아", "어디"]):
        return "searcher"
    return "analyst"

def searcher(state: AgentState):
    print("---SEARCHER: 데이터 수집---")
    # 도구(Tool)를 사용하여 candidates 채우기
    return {"candidates": [{"name": "맛있네식당", "score": 4.5}]}

def filter(state: AgentState):
    print("---FILTER: 데이터 검증---")
    # 평점 4.0 미만 제거 등 로직
    filtered = [c for c in state["candidates"] if c['score'] >= 4.0]
    return {"filtered_candidates": filtered, "retry_count": state["retry_count"] + 1}

def filter_logic(state: AgentState) -> Literal["searcher", "analyst"]:
    # 필터링 결과가 없거나 너무 적으면 다시 검색 (최대 2번)
    if len(state.get("filtered_candidates", [])) == 0 and state["retry_count"] < 2:
        print("---FILTER: 결과 부족으로 재검색 결정---")
        return "searcher"
    return "analyst"

def human_approval(state: AgentState):
    print("--- HUMAN APPROVAL: 사용자의 선택을 기다립니다 ---")
    # 이 노드는 특별한 로직 없이, 중단점(Interrupt) 이후 
    # 사용자가 업데이트한 State를 다음 노드로 넘기는 징검다리 역할을 합니다.
    return state

def analyst(state: AgentState):
    print("---ANALYST: 리뷰 심층 분석---")
    return {"analysis_report": "이곳은 주차가 편리하고 가성비가 좋습니다."}

def writer(state: AgentState):
    print("---WRITER: 최종 답변 작성---")
    return {"final_answer": f"최종 추천 결과: {state['analysis_report']}"}

# 3. 그래프 구성
workflow = StateGraph(AgentState)
# 노드 추가
workflow.add_node("manager", manager)
workflow.add_node("router", router)
workflow.add_node("searcher", searcher)
workflow.add_node("filter", filter)
workflow.add_node("human_approval", human_approval)
workflow.add_node("analyst", analyst)
workflow.add_node("writer", writer)
# 엣지 연결 (일반 엣지 + 조건부 엣지)
workflow.set_entry_point("manager")
# [핵심] Manager 다음에 Router 로직을 태워 분기합니다.
workflow.add_conditional_edges(
    "manager",
    router, # 이 함수가 다음 갈 곳을 결정함
    {
        "searcher": "searcher",
        "analyst": "analyst"
    }
)
workflow.add_edge("searcher", "filter")
workflow.add_edge("filter", "human_approval")
workflow.add_edge("human_approval", "analyst")
workflow.add_edge("analyst", "writer")
workflow.add_edge("writer", END)
# [중요] 체크포인트 설정 및 컴파일
memory = MemorySaver()
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_approval"] # human_approval 노드 실행 직전에 멈춤!
)