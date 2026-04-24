"""
agents.py
---------
모든 LangGraph 노드 함수 정의.

모델 역할 배분:
  qwen3.5:9b     → Manager, Filter  (한국어 파라미터 추출)
  exaone3.5:7.8b → Extractor, Analyst (한국어 문서 분석)
  gemma4:latest  → Collector, Writer  (자연스러운 문장 생성)
"""

import os
import json
import re
from typing import Dict, Any, List, Optional, Type, TypeVar

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.types import interrupt, Command
from pydantic import BaseModel

from schemas import (
    QueryParams, Restaurant, FilterResult,
    RestaurantInsight, ExtractedDetail, HitlAction, FinalSummary,
)
from tools import get_restaurant_search_tool, extract_restaurant_detail, parse_extract_to_prompt

# ────────────────────────────────────────────
# Ollama LLM 설정
# ────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

llm_qwen = ChatOllama(
    model="qwen3.5:9b", base_url=OLLAMA_BASE_URL,
    temperature=0, num_ctx=4096,
)
llm_exaone = ChatOllama(
    model="exaone3.5:7.8b", base_url=OLLAMA_BASE_URL,
    temperature=0.2, format="json", num_ctx=8192,
)
llm_gemma = ChatOllama(
    model="gemma4:latest", base_url=OLLAMA_BASE_URL,
    temperature=0.5, format="json", num_ctx=4096,
)
llm_gemma_text = ChatOllama(
    model="gemma4:latest", base_url=OLLAMA_BASE_URL,
    temperature=0.5, num_ctx=4096,
)

# ────────────────────────────────────────────
# JSON 파싱 헬퍼 (로컬 모델 fallback 대응)
# ────────────────────────────────────────────
T = TypeVar("T", bound=BaseModel)

def parse_structured_output(raw: str, schema: Type[T], fallback: T) -> T:
    # Qwen3 계열 모델의 <think>...</think> 블록 제거
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    for attempt in [
        lambda: json.loads(raw.strip()),
        lambda: json.loads(re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()),
        lambda: json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group()),
    ]:
        try:
            return schema.model_validate(attempt())
        except Exception:
            pass
    print(f"  ⚠️ 파싱 실패 → fallback 사용 | 원문: {raw[:150]}")
    return fallback


# ────────────────────────────────────────────
# 모듈 레벨 LCEL 체인 (호출마다 재생성 방지)
# ────────────────────────────────────────────
_MANAGER_CHAIN = (
    ChatPromptTemplate.from_template("""
사용자 질문에서 정보를 추출하여 반드시 아래 JSON 형식으로만 답하세요.

{{
  "location": "지역명",
  "category": "음식 종류",
  "preferences": ["특징1", "특징2"],
  "max_price": null
}}

질문: {query}
/no_think
""")
    | llm_qwen
    | StrOutputParser()
).with_retry(stop_after_attempt=3)

_FILTER_CHAIN = (
    ChatPromptTemplate.from_template("""
아래 검색 결과는 블로그 포스트입니다. 각 항목에서 실제 식당 정보를 추출하고 품질 낮은 항목을 걸러내세요.

처리 규칙:
1. 제목/내용에서 실제 식당 이름을 추출해 name에 저장 (블로그 제목 그대로 넣지 말 것)
2. 여러 식당을 나열하는 목록형 포스트(Top10, 맛집 목록 등)는 제외
3. 광고성 콘텐츠, 정보 부족 항목 제외
4. score는 내용에서 언급된 실제 평점(별점)이 있으면 사용, 없으면 0.0

반드시 아래 JSON 형식으로만 답하세요:
{{
  "filtered_candidates": [{{"name":"실제식당이름","score":0.0,"review_count":null,"address":null,"category":null,"price_range":null,"source_url":null,"summary":"한줄요약"}}],
  "needs_retry": false,
  "reason": null
}}

후보: {candidates}
결과 2개 미만이면 needs_retry를 true로 설정하세요.
/no_think
""")
    | llm_qwen
    | StrOutputParser()
).with_retry(stop_after_attempt=3)

_EXTRACTOR_CHAIN = (
    ChatPromptTemplate.from_template("""
크롤링 텍스트에서 식당 정보를 추출하세요. 식당: {name}

{{
  "name": "{name}",
  "source_url": "{url}",
  "menu_items": [],
  "opening_hours": null,
  "price_range": null,
  "highlights": [],
  "raw_text": null
}}

내용: {raw_text}
""")
    | llm_exaone
    | StrOutputParser()
).with_retry(stop_after_attempt=3)

_ANALYST_CHAIN = (
    ChatPromptTemplate.from_template("""
식당을 분석하세요.

선호도: {preferences} / 예산: {max_price}
이름: {name} / 평점: {score} / 요약: {summary}
메뉴: {menu_items} / 영업시간: {opening_hours}
가격대: {price_range} / 특징: {highlights}

반드시 JSON으로만:
{{
  "name": "{name}",
  "pros": ["장점1","장점2"],
  "cons": ["단점1"],
  "recommendation_reason": "추천 이유 한 문장",
  "best_menu": null
}}
""")
    | llm_exaone
    | StrOutputParser()
).with_retry(stop_after_attempt=3)

_COLLECTOR_CHAIN = (
    ChatPromptTemplate.from_template("""
분석 결과를 종합하세요.
식당들: {insights}
선호도: {preferences}

JSON으로만:
{{"top_pick": "1순위 식당 이름", "summary": "2~3문장 요약"}}
""")
    | llm_gemma
    | StrOutputParser()
).with_retry(stop_after_attempt=3)


# ────────────────────────────────────────────
# 1. MANAGER
# ────────────────────────────────────────────
async def manager(state: Dict[str, Any]) -> Dict[str, Any]:
    print("--- [MANAGER] (qwen3.5:9b) ---")
    raw = await _MANAGER_CHAIN.ainvoke({"query": state["query"]})
    result = parse_structured_output(
        raw, QueryParams,
        QueryParams(location="미정", category="전체", preferences=[])
    )
    return {
        "location": result.location,
        "category": result.category,
        "preferences": result.preferences,
        "max_price": result.max_price,
        "retry_count": 0,
    }


# ────────────────────────────────────────────
# 2. ROUTER (조건부 엣지 함수)
# ────────────────────────────────────────────
def router_logic(state: Dict[str, Any]) -> str:
    location = state.get("location", "")
    category = state.get("category", "")
    # Manager 파싱 실패 fallback 값("미정", "전체")이면 검색 불가 → analyst(collector)로
    has_location = bool(location) and location not in ("미정", "")
    has_category = bool(category) and category not in ("전체", "")
    if has_location or has_category:
        return "searcher"
    return "analyst"


# ────────────────────────────────────────────
# 3. SEARCHER
# ────────────────────────────────────────────
async def searcher(state: Dict[str, Any]) -> Dict[str, Any]:
    print(f"--- [SEARCHER] {state.get('location')} {state.get('category')} ---")

    tool = get_restaurant_search_tool()
    raw_results = await tool.ainvoke({"query": f"{state['location']} {state['category']} 맛집 평점 리뷰"})

    candidates = []
    for item in raw_results:
        try:
            candidates.append(Restaurant(
                name=item.get("title", "이름 없음"),
                score=float(item.get("score", 0.0)),
                source_url=item.get("url"),
                summary=item.get("content", "")[:300],
            ).model_dump())
        except Exception:
            continue

    return {"candidates": candidates}


# ────────────────────────────────────────────
# 4. FILTER
# ────────────────────────────────────────────
async def filter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    print("--- [FILTER] (qwen3.5:9b) ---")

    raw_candidates = state.get("candidates", [])
    raw = await _FILTER_CHAIN.ainvoke({"candidates": json.dumps(raw_candidates, ensure_ascii=False)})
    result = parse_structured_output(
        raw, FilterResult,
        FilterResult(
            filtered_candidates=[Restaurant(**c) for c in raw_candidates[:5]],
            needs_retry=len(raw_candidates) < 2,
        )
    )
    return {
        "filtered_candidates": [r.model_dump() for r in result.filtered_candidates],
        "needs_retry": result.needs_retry,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def filter_logic(state: Dict[str, Any]) -> str:
    if state.get("needs_retry") and state.get("retry_count", 0) < 2:
        return "searcher"
    return "human_approval"


# ────────────────────────────────────────────
# 5. HUMAN APPROVAL (Command API HITL)
#
# interrupt()로 후보 리스트를 전달하며 중단.
# 웹: chat.py가 Command(resume=HitlAction(...))로 재개.
# ────────────────────────────────────────────
def human_approval(state: Dict[str, Any]) -> Command:
    print("--- [HUMAN APPROVAL] interrupt 발생 ---")

    response: HitlAction = interrupt({
        "candidates": state.get("filtered_candidates", []),
        "message": "분석할 식당을 선택하거나 재검색을 요청하세요.",
    })

    if response.action in ("approve", "modify"):
        print(f"  ✅ {response.action}: {response.selected_indices}")
        return Command(
            update={"selected_indices": response.selected_indices, "insights": []},
            goto="dispatch",
        )

    # reject → 재검색
    print(f"  ❌ reject: 재검색 (feedback: {response.feedback})")
    updated_query = state.get("query", "")
    if response.feedback:
        updated_query = f"{updated_query} {response.feedback}"
    return Command(
        update={
            "query": updated_query,
            "candidates": [],
            "filtered_candidates": [],
            "retry_count": 0,
            "needs_retry": False,
        },
        goto="searcher",
    )


# ────────────────────────────────────────────
# 6-A. EXTRACTOR (서브그래프 노드 1)
# ────────────────────────────────────────────
async def extract_single(state: dict) -> dict:
    restaurant = state.get("restaurant", {})
    name = restaurant.get("name", "알 수 없음")
    url  = restaurant.get("source_url")

    print(f"  🔍 [EXTRACTOR] '{name}' (exaone3.5:7.8b)")

    prompt_text = parse_extract_to_prompt(
        extract_restaurant_detail([url]) if url else [], name
    )

    raw = await _EXTRACTOR_CHAIN.ainvoke({
        "name": name, "url": url or "", "raw_text": prompt_text[:3000],
    })
    result = parse_structured_output(raw, ExtractedDetail, ExtractedDetail(name=name, source_url=url or ""))
    return {**state, "extracted_detail": result.model_dump()}


# ────────────────────────────────────────────
# 6-B. ANALYST_SINGLE (서브그래프 노드 2)
# ────────────────────────────────────────────
async def analyst_single(state: dict) -> dict:
    restaurant = state.get("restaurant", {})
    detail     = state.get("extracted_detail", {})
    name       = restaurant.get("name", "알 수 없음")

    print(f"  🧠 [ANALYST] '{name}' (exaone3.5:7.8b)")

    raw = await _ANALYST_CHAIN.ainvoke({
        "preferences": state.get("preferences", []),
        "max_price":   state.get("max_price", "제한 없음"),
        "name":        name,
        "score":       restaurant.get("score", "N/A"),
        "summary":     restaurant.get("summary", ""),
        "menu_items":  detail.get("menu_items", []),
        "opening_hours": detail.get("opening_hours", "정보 없음"),
        "price_range": detail.get("price_range", "정보 없음"),
        "highlights":  detail.get("highlights", []),
    })
    result = parse_structured_output(
        raw, RestaurantInsight,
        RestaurantInsight(name=name, pros=["정보 부족"], cons=[], recommendation_reason="추가 확인 필요")
    )
    return {**state, "insight": result.model_dump()}


# ────────────────────────────────────────────
# 6-C. COLLECTOR
# ────────────────────────────────────────────
async def collector(state: dict) -> dict:
    print("--- [COLLECTOR] (gemma4:latest) ---")

    insights = state.get("insights", [])
    if not insights:
        return {"analysis_report": {"insights": [], "top_pick": "없음", "summary": "결과 없음."}}

    raw = await _COLLECTOR_CHAIN.ainvoke({
        "insights": str(insights),
        "preferences": state.get("preferences", []),
    })
    final = parse_structured_output(
        raw, FinalSummary,
        FinalSummary(top_pick=insights[0].get("name", "없음"), summary="분석 완료.")
    )
    return {"analysis_report": {"insights": insights, "top_pick": final.top_pick, "summary": final.summary}}


# ────────────────────────────────────────────
# 7. WRITER
# ────────────────────────────────────────────
def writer(state: Dict[str, Any]) -> Dict[str, Any]:
    print("--- [WRITER] (gemma4:latest) ---")

    report   = state.get("analysis_report", {})
    insights = report.get("insights", [])
    top_pick = report.get("top_pick", "")
    summary  = report.get("summary", "")

    lines = ["🍽️ AI 맛집 추천 리포트", "=" * 40, ""]
    for idx, insight in enumerate(insights, 1):
        lines.append(f"[{idx}위] {insight.get('name', '')}")
        if insight.get("best_menu"):
            lines.append(f"  🍜 대표 메뉴: {insight['best_menu']}")
        lines.append(f"  ✅ 장점: {', '.join(insight.get('pros', []))}")
        lines.append(f"  ⚠️  단점: {', '.join(insight.get('cons', []))}")
        lines.append(f"  💬 추천 이유: {insight.get('recommendation_reason', '')}")
        lines.append("")
    lines += ["=" * 40, f"🏆 최종 픽: {top_pick}", f"📝 요약: {summary}"]

    return {"final_answer": "\n".join(lines)}
