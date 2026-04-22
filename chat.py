"""
chat.py
-------
FastAPI 라우터. SSE(Server-Sent Events)로 LangGraph 진행 상황 실시간 전송.

엔드포인트:
  GET  /api/chat/start/stream   → 검색~필터 진행상황 스트리밍 + candidates
  GET  /api/chat/select/stream  → 분석 진행상황 스트리밍 + final_answer
  POST /api/chat/reject         → 재검색 (빠른 응답, SSE 불필요)

SSE 이벤트 타입:
  progress → 노드 완료 알림  {"node": "manager", "label": "질문 분석 완료"}
  result   → 최종 데이터     {"candidates": [...]} or {"final_answer": "..."}
  error    → 오류 메시지     {"message": "..."}
"""

import uuid
import json
import asyncio
from typing import List, Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.types import Command

from graph import app as langgraph_app
from schemas import HitlAction

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ────────────────────────────────────────────
# 노드 → 사용자 친화적 라벨 매핑
# ────────────────────────────────────────────
NODE_LABELS = {
    "manager":             "📋 질문 분석 완료",
    "searcher":            "🔎 맛집 검색 완료",
    "filter":              "🧹 데이터 필터링 완료",
    "restaurant_subgraph": "🍽️  식당 분석 완료",
    "collector":           "📊 결과 취합 완료",
    "writer":              "✍️  리포트 작성 완료",
}


# ────────────────────────────────────────────
# SSE 이벤트 포맷 헬퍼
# ────────────────────────────────────────────
def sse_event(event_type: str, data: dict) -> str:
    """
    SSE 표준 포맷으로 직렬화.
    브라우저의 EventSource가 파싱할 수 있는 형태.

    형식:
      event: progress
      data: {"node": "manager", "label": "질문 분석 완료"}
      (빈 줄)
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_progress(node: str, label: str, extra: dict = {}) -> str:
    return sse_event("progress", {"node": node, "label": label, **extra})


def sse_result(data: dict) -> str:
    return sse_event("result", data)


def sse_error(message: str) -> str:
    return sse_event("error", {"message": message})


# ────────────────────────────────────────────
# 요청/응답 스키마 (POST용)
# ────────────────────────────────────────────
class RejectRequest(BaseModel):
    thread_id: str
    feedback:  Optional[str] = None

class RejectResponse(BaseModel):
    thread_id:  str
    candidates: List[dict]
    status:     str


# ────────────────────────────────────────────
# 1. 검색 스트리밍: GET /start/stream
#    Manager → Searcher → Filter 진행상황 실시간 전송
#    interrupt() 발생 시 candidates를 result 이벤트로 전송
# ────────────────────────────────────────────
@router.get("/start/stream")
async def start_stream(query: str = Query(..., description="검색 질문")):
    """
    새 세션 시작 + SSE 스트리밍.

    클라이언트는 EventSource로 연결:
      const es = new EventSource(`/api/chat/start/stream?query=...`)
      es.addEventListener("progress", e => ...)
      es.addEventListener("result",   e => { data = JSON.parse(e.data) })
    """
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    async def generate() -> AsyncGenerator[str, None]:
        try:
            completed_subgraphs = 0

            async for event in langgraph_app.astream_events(
                {"query": query, "insights": []},
                config,
                version="v2",
            ):
                name = event.get("name", "")
                kind = event.get("event", "")

                # interrupt 감지 → 루프 탈출
                if name == "__interrupt__":
                    break

                # 노드 완료 → progress 이벤트 전송
                if kind == "on_chain_end" and name in NODE_LABELS:
                    if name == "restaurant_subgraph":
                        completed_subgraphs += 1
                        yield sse_progress(name, f"🍽️  식당 분석 완료 ({completed_subgraphs}번째)")
                    else:
                        yield sse_progress(name, NODE_LABELS[name])

            # 최종 상태에서 candidates 추출 → result 이벤트
            state      = langgraph_app.get_state(config)
            candidates = state.values.get("filtered_candidates", [])

            if not candidates:
                yield sse_result({"thread_id": thread_id, "candidates": [], "status": "no_results"})
            else:
                yield sse_result({
                    "thread_id": thread_id,
                    "candidates": candidates,
                    "status": "waiting_selection",
                })

        except asyncio.CancelledError:
            # 클라이언트가 연결을 끊은 경우 (정상)
            pass
        except Exception as e:
            yield sse_error(f"검색 중 오류 발생: {str(e)}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Nginx 버퍼링 비활성화
            "Connection": "keep-alive",
        },
    )


# ────────────────────────────────────────────
# 2. 분석 스트리밍: GET /select/stream
#    Command(resume=HitlAction) → dispatch → 병렬 분석 → Writer
#    각 노드 완료마다 progress, 최종 리포트를 result로 전송
# ────────────────────────────────────────────
@router.get("/select/stream")
async def select_stream(
    thread_id:        str       = Query(...),
    selected_indices: str       = Query(..., description="쉼표 구분 인덱스. 예: 0,2"),
    action:           str       = Query("approve", description="approve | modify"),
):
    """
    식당 선택 후 분석 재개 + SSE 스트리밍.

    클라이언트:
      const es = new EventSource(`/api/chat/select/stream?thread_id=...&selected_indices=0,1`)
    """
    # 인덱스 파싱
    try:
        indices = [int(x.strip()) for x in selected_indices.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="selected_indices 형식 오류. 예: 0,2")

    config = {"configurable": {"thread_id": thread_id}}

    # 세션 유효성 확인
    state = langgraph_app.get_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    hitl_response = HitlAction(action=action, selected_indices=indices)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            completed_subgraphs = 0
            total = len(indices)

            async for event in langgraph_app.astream_events(
                Command(resume=hitl_response),
                config,
                version="v2",
            ):
                name = event.get("name", "")
                kind = event.get("event", "")

                # 노드 완료 → progress 이벤트
                if kind == "on_chain_end" and name in NODE_LABELS:
                    if name == "restaurant_subgraph":
                        completed_subgraphs += 1
                        yield sse_progress(
                            name,
                            f"🍽️  식당 분석 완료 ({completed_subgraphs}/{total})",
                            {"completed": completed_subgraphs, "total": total},
                        )
                    else:
                        yield sse_progress(name, NODE_LABELS[name])

            # 최종 결과 → result 이벤트
            final_state  = langgraph_app.get_state(config)
            final_answer = final_state.values.get("final_answer", "결과를 가져오지 못했습니다.")
            candidates   = final_state.values.get("filtered_candidates", [])

            yield sse_result({
                "thread_id":    thread_id,
                "final_answer": final_answer,
                "candidates":   candidates,
                "status":       "done",
            })

        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield sse_error(f"분석 중 오류 발생: {str(e)}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ────────────────────────────────────────────
# 3. 거절 후 재검색: POST /reject
#    빠른 응답이므로 SSE 불필요
#    완료 후 클라이언트가 /start/stream으로 새 스트림 연결
# ────────────────────────────────────────────
@router.post("/reject", response_model=RejectResponse)
async def reject_and_research(req: RejectRequest):
    """
    후보 전체 거절 + 추가 조건으로 재검색.
    reject → searcher → filter → interrupt() 까지 실행 후 새 candidates 반환.
    """
    config = {"configurable": {"thread_id": req.thread_id}}

    state = langgraph_app.get_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    hitl_response = HitlAction(action="reject", feedback=req.feedback)

    async for event in langgraph_app.astream_events(
        Command(resume=hitl_response),
        config,
        version="v2",
    ):
        if event.get("name") == "__interrupt__":
            break

    new_state  = langgraph_app.get_state(config)
    candidates = new_state.values.get("filtered_candidates", [])

    return RejectResponse(
        thread_id=req.thread_id,
        candidates=candidates,
        status="waiting_selection" if candidates else "no_results",
    )