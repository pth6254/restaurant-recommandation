from typing import TypedDict, List, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents import manager, searcher, filter_node, analyst, writer
from agents import router_logic, filter_logic

# ── 상태 정의 ──────────────────────────────────────────────
class AgentState(TypedDict):
    query:               str
    location:            Optional[str]
    category:            Optional[str]
    preferences:         List[str]
    max_price:           Optional[int]
    candidates:          List[dict]
    filtered_candidates: List[dict]
    selected_indices:    Optional[List[int]]
    analysis_report:     Optional[str]
    final_answer:        Optional[str]
    retry_count:         int

# ── Human-Approval 노드 (징검다리) ─────────────────────────
def human_approval(state: AgentState):
    """중단점 이후 사용자가 주입한 selected_indices를 그대로 전달"""
    return state

# ── 그래프 구성 ────────────────────────────────────────────
workflow = StateGraph(AgentState)

workflow.add_node("manager",        manager)
workflow.add_node("searcher",       searcher)
workflow.add_node("filter",         filter_node)
workflow.add_node("human_approval", human_approval)
workflow.add_node("analyst",        analyst)
workflow.add_node("writer",         writer)

workflow.set_entry_point("manager")

workflow.add_conditional_edges(
    "manager",
    router_logic,
    {"searcher": "searcher", "analyst": "analyst"}
)

workflow.add_edge("searcher", "filter")

workflow.add_conditional_edges(
    "filter",
    filter_logic,
    {"searcher": "searcher", "human_approval": "human_approval"}
)

workflow.add_edge("human_approval", "analyst")
workflow.add_edge("analyst", "writer")
workflow.add_edge("writer", END)

memory  = MemorySaver()
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_approval"]
)

# langgraph.json 호환용 alias
main_agent = app
