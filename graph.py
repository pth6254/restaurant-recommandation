"""
graph.py
--------
LangGraph 워크플로우 설계도 (웹 앱용).

흐름:
  Manager → Searcher → Filter → Human_Approval[interrupt]
    approve/modify → dispatch → restaurant_subgraph (병렬) → Collector → Writer
    reject         → Searcher (재검색)
"""

import operator
import os
from typing import TypedDict, List, Optional, Annotated

from langgraph.graph import StateGraph, END
from langgraph.types import Send

from agents import (
    manager, router_logic, searcher,
    filter_node, filter_logic,
    human_approval,
    extract_single, analyst_single,
    collector, writer,
)


# ────────────────────────────────────────────
# 상태 정의
# ────────────────────────────────────────────
class AgentState(TypedDict):
    query:               str
    location:            Optional[str]
    category:            Optional[str]
    preferences:         List[str]
    max_price:           Optional[int]
    candidates:          List[dict]
    filtered_candidates: List[dict]
    needs_retry:         bool
    selected_indices:    List[int]
    insights:            Annotated[List[dict], operator.add]  # 병렬 결과 자동 누적
    analysis_report:     Optional[dict]
    final_answer:        Optional[str]
    retry_count:         int


class SubgraphState(TypedDict):
    restaurant:       dict
    preferences:      List[str]
    max_price:        Optional[int]
    extracted_detail: Optional[dict]
    insight:          Optional[dict]


# ────────────────────────────────────────────
# 서브그래프 (식당 1개: Extract → Analyst)
# ────────────────────────────────────────────
def build_restaurant_subgraph():
    sub = StateGraph(SubgraphState)
    sub.add_node("extractor",     extract_single)
    sub.add_node("analyst_single", analyst_single)
    sub.set_entry_point("extractor")
    sub.add_edge("extractor", "analyst_single")
    sub.add_edge("analyst_single", END)
    return sub.compile()

restaurant_subgraph = build_restaurant_subgraph()


# ────────────────────────────────────────────
# dispatch 노드: selected_indices → Send() 병렬 발행
# human_approval의 Command(goto="dispatch") 이후 실행
# ────────────────────────────────────────────
def dispatch_to_subgraphs(state: AgentState) -> List[Send]:
    selected  = state.get("selected_indices", [0])
    all_cands = state.get("filtered_candidates", [])
    targets   = [all_cands[i] for i in selected if i < len(all_cands)] or all_cands[:3]

    print(f"--- [DISPATCH] {len(targets)}개 식당 병렬 분석 ---")
    return [
        Send("restaurant_subgraph", {
            "restaurant":  r,
            "preferences": state.get("preferences", []),
            "max_price":   state.get("max_price"),
        })
        for r in targets
    ]


async def run_restaurant_subgraph(state: SubgraphState) -> dict:
    result  = await restaurant_subgraph.ainvoke(state)
    insight = result.get("insight")
    return {"insights": [insight]} if insight else {"insights": []}


# ────────────────────────────────────────────
# 메인 그래프 구성
# ────────────────────────────────────────────
workflow = StateGraph(AgentState)

workflow.add_node("manager",             manager)
workflow.add_node("searcher",            searcher)
workflow.add_node("filter",              filter_node)
workflow.add_node("human_approval",      human_approval)
workflow.add_node("dispatch",            lambda s: s)       # 상태 통과, Send()로 분기
workflow.add_node("restaurant_subgraph", run_restaurant_subgraph)
workflow.add_node("collector",           collector)
workflow.add_node("writer",              writer)

workflow.set_entry_point("manager")

workflow.add_conditional_edges("manager", router_logic,
    {"searcher": "searcher", "analyst": "collector"})

workflow.add_edge("searcher", "filter")

workflow.add_conditional_edges("filter", filter_logic,
    {"searcher": "searcher", "human_approval": "human_approval"})

# human_approval → Command(goto="dispatch" or "searcher")
# Command API가 실제 라우팅을 처리; 아래는 그래프 노드 연결 선언용
workflow.add_conditional_edges(
    "human_approval",
    lambda s: "dispatch",   # 런타임에 호출되지 않음 — Command(goto=...) 가 우선
    {"dispatch": "dispatch", "searcher": "searcher"},
)

# dispatch → Send() → restaurant_subgraph (병렬)
workflow.add_conditional_edges("dispatch", dispatch_to_subgraphs,
    ["restaurant_subgraph"])

workflow.add_edge("restaurant_subgraph", "collector")
workflow.add_edge("collector", "writer")
workflow.add_edge("writer", END)


DB_PATH = os.getenv("CHECKPOINT_DB_PATH", "./data/checkpoints.db")