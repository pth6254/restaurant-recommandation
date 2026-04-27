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
from tools import (
    RESTAURANT_SEARCH_TOOL, extract_restaurant_detail, parse_extract_to_prompt,
    search_restaurants_kakao, search_restaurant_reviews,
)

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
    temperature=0.2, format="json", num_ctx=4096,
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

# 목록형 블로그 포스트 제목 패턴 (LLM 없이 Python으로 필터링)
_LIST_PATTERNS = re.compile(
    r"(top\s*\d+|순위|맛집\s*(리스트|모음|추천|정리|베스트)|best\s*\d+|\d+\s*곳|\d+\s*선)",
    re.IGNORECASE,
)

# Tavily 후보 정제: 상호명 추출 + 리뷰 요약 (배치, 한 번 호출)
_CANDIDATE_REFINE_CHAIN = (
    ChatPromptTemplate.from_template("""
검색어: {location} {category} 맛집

아래 검색 결과 각각에 대해 분석하세요.
- restaurant_name: 단일 식당을 소개하는 글이면 식당 상호명, 여러 식당 목록글이면 null
- summary: 해당 식당의 분위기·맛·특징을 리뷰 내용 기반으로 2문장 이내로 요약. 목록글이면 null

결과:
{results}

JSON으로만 출력:
{{"items": [{{"idx": 0, "restaurant_name": "상호명 또는 null", "summary": "요약 또는 null"}}, ...]}}
/no_think
""")
    | llm_qwen
    | StrOutputParser()
).with_retry(stop_after_attempt=2)


def _parse_refine_output(raw: str, count: int) -> list:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    for attempt in [
        lambda: json.loads(raw),
        lambda: json.loads(re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()),
        lambda: json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group()),
    ]:
        try:
            obj = attempt()
            items = obj.get("items", obj) if isinstance(obj, dict) else obj
            if isinstance(items, list):
                items.sort(key=lambda x: x.get("idx", 0))
                return items
        except Exception:
            pass
    return [{"idx": i, "restaurant_name": None, "summary": None} for i in range(count)]

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
    location = state.get("location", "")
    category = state.get("category", "")
    print(f"--- [SEARCHER] {location} {category} ---")

    # 1차: 카카오 로컬 API — 상호명·주소·좌표 정확, 카테고리 보장
    kakao_results = await search_restaurants_kakao(location, category)
    if kakao_results:
        candidates = []
        for item in kakao_results:
            try:
                candidates.append(Restaurant(
                    name=item["name"],
                    address=item.get("address"),
                    category=item.get("category"),
                    source_url=item.get("source_url"),
                    x=item.get("x"),
                    y=item.get("y"),
                ).model_dump())
            except Exception:
                continue
        print(f"  ✅ 카카오 로컬: {len(candidates)}개")
        return {"candidates": candidates}

    # 2차 fallback: Tavily (KAKAO_REST_API_KEY 미설정 시)
    print("  ⚠️ 카카오 API 미설정 → Tavily fallback")
    raw_results = await RESTAURANT_SEARCH_TOOL.ainvoke(
        {"query": f"{location} {category} 맛집 평점 리뷰"}
    )
    if not raw_results:
        return {"candidates": []}

    # LLM 배치 호출: 상호명 추출 + 리뷰 요약 생성
    results_text = "\n".join(
        f"[{i}] 제목: {r.get('title', '')}\n    내용: {r.get('content', '')[:200]}"
        for i, r in enumerate(raw_results)
    )
    try:
        raw = await _CANDIDATE_REFINE_CHAIN.ainvoke({
            "location": location,
            "category": category,
            "results": results_text,
        })
        refine_list = _parse_refine_output(raw, len(raw_results))
    except Exception as e:
        print(f"  ⚠️ 후보 정제 실패 (원본 유지): {e}")
        refine_list = [{"idx": i, "restaurant_name": None, "summary": None} for i in range(len(raw_results))]

    candidates = []
    for i, (item, refined) in enumerate(zip(raw_results, refine_list)):
        name = refined.get("restaurant_name")
        if not name:  # 목록글 또는 단일 식당 특정 불가 → 제외
            print(f"  ❌ 목록글 제외: {item.get('title', '')[:40]}")
            continue
        try:
            candidates.append(Restaurant(
                name=name,
                score=float(item.get("score", 0.0)),
                source_url=item.get("url"),
                summary=refined.get("summary") or item.get("content", "")[:300],
            ).model_dump())
        except Exception:
            continue

    print(f"  ✅ 정제 후 후보: {len(candidates)}개")
    return {"candidates": candidates}


# ────────────────────────────────────────────
# 4. FILTER (Python 기반 — LLM 호출 없음)
# ────────────────────────────────────────────
def filter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    print("--- [FILTER] (Python) ---")

    filtered = []
    for item in state.get("candidates", []):
        title   = (item.get("name") or "").strip()
        content = (item.get("summary") or "").strip()

        if _LIST_PATTERNS.search(title):   # 목록형 블로그 포스트 제외
            continue
        if len(content) < 30:              # 내용 너무 짧으면 제외
            continue

        filtered.append({
            "name":        title,
            "score":       float(item.get("score", 0.0)),
            "source_url":  item.get("source_url") or "",
            "summary":     content[:300],
            "address":     item.get("address"),
            "category":    item.get("category"),
            "price_range": item.get("price_range"),
            "review_count": item.get("review_count"),
        })

    return {
        "filtered_candidates": filtered[:8],
        "needs_retry":         len(filtered) < 2,
        "retry_count":         state.get("retry_count", 0) + 1,
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

    extracted = await extract_restaurant_detail([url]) if url else []
    prompt_text = parse_extract_to_prompt(extracted, name)

    # 카카오 place URL은 리뷰 내용이 없으므로 Tavily 리뷰 검색으로 보완
    is_kakao_url = url and "place.map.kakao.com" in url
    if is_kakao_url or len(prompt_text) < 100:
        location_hint = (restaurant.get("address") or "").split()[0]
        review_text = await search_restaurant_reviews(name, location_hint)
        if review_text:
            prompt_text = review_text

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
