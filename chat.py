from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from graph import app as langgraph_app
from db.database import get_db, Conversation

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── 요청/응답 스키마 ───────────────────────────────────────
class StartRequest(BaseModel):
    query: str

class StartResponse(BaseModel):
    thread_id:  str
    candidates: List[dict]
    status:     str   # "waiting_selection" | "done" | "no_results"

class SelectRequest(BaseModel):
    thread_id:       str
    selected_indices: List[int]

class SelectResponse(BaseModel):
    thread_id:    str
    final_answer: str
    candidates:   List[dict]
    status:       str

# ── 1단계: 검색 시작 ──────────────────────────────────────
@router.post("/start", response_model=StartResponse)
async def start_chat(req: StartRequest, db: AsyncSession = Depends(get_db)):
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    # Manager → Searcher → Filter → (interrupt_before human_approval)
    async for _ in langgraph_app.astream({"query": req.query}, config):
        pass

    state      = langgraph_app.get_state(config)
    candidates = state.values.get("filtered_candidates", [])

    if not candidates:
        return StartResponse(
            thread_id=thread_id,
            candidates=[],
            status="no_results"
        )

    # DB에 대화 저장
    conv = Conversation(
        thread_id=thread_id,
        query=req.query,
        result=None
    )
    db.add(conv)
    await db.commit()

    return StartResponse(
        thread_id=thread_id,
        candidates=candidates,
        status="waiting_selection"
    )

# ── 2단계: 식당 선택 후 분석 재개 ─────────────────────────
@router.post("/select", response_model=SelectResponse)
async def select_restaurants(req: SelectRequest, db: AsyncSession = Depends(get_db)):
    config = {"configurable": {"thread_id": req.thread_id}}

    # 선택한 인덱스를 state에 주입
    langgraph_app.update_state(config, {"selected_indices": req.selected_indices})

    # human_approval → Analyst → Writer
    async for _ in langgraph_app.astream(None, config):
        pass

    state        = langgraph_app.get_state(config)
    final_answer = state.values.get("final_answer", "결과를 가져오지 못했습니다.")
    candidates   = state.values.get("filtered_candidates", [])

    # DB 업데이트
    result = await db.execute(
        select(Conversation).where(Conversation.thread_id == req.thread_id)
    )
    conv = result.scalar_one_or_none()
    if conv:
        conv.result = {"final_answer": final_answer, "candidates": candidates}
        await db.commit()

    return SelectResponse(
        thread_id=req.thread_id,
        final_answer=final_answer,
        candidates=candidates,
        status="done"
    )
