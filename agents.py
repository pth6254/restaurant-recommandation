"""
agents/agents.py
----------------
모델 역할 배분:
  QWEN3.5:9B    → Manager, Filter        (한국어 파라미터 추출·판단 강점)
  EXAONE3.5:7.8B → Extractor, Analyst   (LG AI, 한국어 문서 분석 특화)
  GEMMA4:LATEST  → Collector, Writer    (자연스러운 한국어 문장 생성)

주의: 로컬 모델은 structured_output JSON 신뢰도가 낮으므로
      parse_structured_output() 헬퍼로 fallback 파싱을 추가함.
"""

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Type, TypeVar
import sys
import os
import json
import re

import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schemas import QueryParams, Restaurant, FilterResult, AnalysisReport, RestaurantInsight, ExtractedDetail, SingleRestaurantState
from langchain_community.tools.tavily_search import TavilySearchResults


# ════════════════════════════════════════════
# 검색 도구 (구 tools/search_api.py 통합)
# ════════════════════════════════════════════

def get_restaurant_search_tool():
    """식당 후보 목록 검색용 Tavily Search 도구 반환."""
    return TavilySearchResults(k=10, search_depth="advanced")


def extract_restaurant_detail(urls: List[str]) -> List[dict]:
    """
    Tavily Extract API로 식당 URL 본문을 직접 크롤링.
    Search snippet(~200자) 대신 메뉴·영업시간·가격 등 전체 페이지 추출.
    실패 시 빈 리스트 반환 → 파이프라인 중단 없이 fallback 진행.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("  ⚠️ TAVILY_API_KEY 없음 - Extract 스킵")
        return []

    valid_urls = [u for u in urls if u and u.startswith("http")]
    if not valid_urls:
        return []

    try:
        response = requests.post(
            "https://api.tavily.com/extract",
            json={"api_key": api_key, "urls": valid_urls[:20]},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "url": item.get("url", ""),
                "raw_content": item.get("raw_content", "")[:2000],
                "failed": False,
            })
        for item in data.get("failed_results", []):
            print(f"  ⚠️ Extract 실패: {item.get('url', '')}")
            results.append({"url": item.get("url", ""), "raw_content": "", "failed": True})

        return results

    except requests.exceptions.Timeout:
        print("  ⚠️ Tavily Extract 타임아웃 - 기본 데이터로 계속 진행")
        return []
    except Exception as e:
        print(f"  ⚠️ Tavily Extract 오류: {e} - 기본 데이터로 계속 진행")
        return []


def parse_extract_to_prompt(extract_results: List[dict], restaurant_name: str) -> str:
    """Extract 원문을 LLM 프롬프트 삽입용 텍스트로 정제."""
    if not extract_results:
        return "상세 크롤링 데이터 없음 - 검색 결과 요약 기반으로 분석하세요."

    lines = []
    for item in extract_results:
        if item.get("failed") or not item.get("raw_content"):
            continue
        lines.append(f"[출처: {item['url']}]")
        lines.append(item["raw_content"][:1000])
        lines.append("")

    return "\n".join(lines) if lines else "크롤링 성공했으나 본문 내용 없음."

# ────────────────────────────────────────────
# Ollama 모델 설정
# ────────────────────────────────────────────
# Ollama 기본 주소: http://localhost:11434
# 변경이 필요하면 .env에 OLLAMA_BASE_URL=http://... 설정
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# 역할별 모델 배분
# - num_ctx: 컨텍스트 윈도우 크기 (크롤링 텍스트를 다루는 노드는 더 크게)
# - temperature=0: 판단/추출 노드는 일관성 우선
# - format="json": Ollama의 JSON 모드 활성화 (structured output 보조)

llm_qwen = ChatOllama(       # Manager, Filter: 한국어 구조화 추출
    model="qwen3.5:9b",
    base_url=OLLAMA_BASE_URL,
    temperature=0,
    format="json",
    num_ctx=4096,
)

llm_exaone = ChatOllama(     # Extractor, Analyst: 한국어 문서 심층 분석
    model="exaone3.5:7.8b",
    base_url=OLLAMA_BASE_URL,
    temperature=0.2,
    format="json",
    num_ctx=8192,            # 크롤링 텍스트 처리를 위해 넉넉하게
)

llm_gemma = ChatOllama(      # Collector, Writer: 자연스러운 문장 생성
    model="gemma4:latest",
    base_url=OLLAMA_BASE_URL,
    temperature=0.5,
    format="json",           # Collector는 JSON, Writer는 아래서 format 없이 별도 인스턴스 사용
    num_ctx=4096,
)

llm_gemma_text = ChatOllama( # Writer 전용: 자유 형식 텍스트 생성 (JSON 모드 OFF)
    model="gemma4:latest",
    base_url=OLLAMA_BASE_URL,
    temperature=0.5,
    num_ctx=4096,
)

# ────────────────────────────────────────────
# 로컬 모델용 Structured Output 헬퍼
# ────────────────────────────────────────────
T = TypeVar("T", bound=BaseModel)

def parse_structured_output(raw: str, schema: Type[T], fallback: T) -> T:
    """
    로컬 모델의 JSON 출력을 Pydantic 모델로 파싱.
    실패 시 fallback 객체를 반환하여 파이프라인 중단을 방지.

    OpenAI와 달리 로컬 모델은 JSON 포맷이 불완전할 수 있어
    3단계 파싱 전략을 사용:
      1) 직접 json.loads()
      2) ```json ... ``` 코드블록에서 추출
      3) 중괄호 범위로 강제 추출
    """
    # 1단계: 직접 파싱
    try:
        data = json.loads(raw.strip())
        return schema.model_validate(data)
    except Exception:
        pass

    # 2단계: 마크다운 코드블록 제거 후 파싱
    try:
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        data = json.loads(cleaned)
        return schema.model_validate(data)
    except Exception:
        pass

    # 3단계: 텍스트에서 첫 번째 JSON 객체 범위 추출
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return schema.model_validate(data)
    except Exception:
        pass

    print(f"  ⚠️  구조화 파싱 실패 → fallback 사용\n  원문: {raw[:200]}")
    return fallback


# ────────────────────────────────────────────
# 1. MANAGER: 질문 분석 및 파라미터 추출
# ────────────────────────────────────────────
def manager(state: Dict[str, Any]):
    print("--- [MANAGER] 질문 분석 중... (qwen3.5:9b) ---")

    # 로컬 모델용 프롬프트: JSON 출력 형식을 명시적으로 지정
    prompt = ChatPromptTemplate.from_template("""
당신은 맛집 추천 시스템의 매니저입니다.
사용자 질문에서 정보를 추출하여 반드시 아래 JSON 형식으로만 답하세요.
다른 텍스트는 절대 포함하지 마세요.

출력 형식:
{{
  "location": "지역명 (예: 강남역)",
  "category": "음식 종류 (예: 일식)",
  "preferences": ["특징1", "특징2"],
  "max_price": null 또는 숫자
}}

사용자 질문: {query}
""")

    chain = prompt | llm_qwen | StrOutputParser()
    raw = chain.invoke({"query": state["query"]})

    fallback = QueryParams(location="미정", category="전체", preferences=[])
    result = parse_structured_output(raw, QueryParams, fallback)

    return {
        "location": result.location,
        "category": result.category,
        "preferences": result.preferences,
        "max_price": result.max_price,
        "retry_count": 0,
    }


# ────────────────────────────────────────────
# 2. ROUTER: 실행 경로 결정 (조건부 엣지용)
# ────────────────────────────────────────────
def router(state: Dict[str, Any]) -> str:
    print("--- [ROUTER] 경로 판단 중... ---")
    if state.get("location") and state.get("category"):
        return "searcher"
    return "analyst"


# ────────────────────────────────────────────
# 3. SEARCHER: Tavily로 실시간 데이터 수집
# ────────────────────────────────────────────
def searcher(state: Dict[str, Any]):
    print(f"--- [SEARCHER] {state['location']} {state['category']} 검색 중... ---")

    search_tool = get_restaurant_search_tool()
    query = f"{state['location']} {state['category']} 맛집 평점 리뷰"
    raw_results = search_tool.invoke({"query": query})

    # Tavily 결과를 Restaurant Pydantic 모델로 변환
    # - 변환 실패 항목은 건너뜀 (프로세스 중단 없음)
    candidates = []
    for item in raw_results:
        try:
            restaurant = Restaurant(
                name=item.get("title", "이름 없음"),
                score=float(item.get("score", 0.0)),
                source_url=item.get("url"),
                summary=item.get("content", "")[:300],
            )
            candidates.append(restaurant)
        except Exception as e:
            print(f"  ⚠️ 식당 데이터 변환 실패 (건너뜀): {e}")
            continue

    return {"candidates": [c.model_dump() for c in candidates]}


# ────────────────────────────────────────────
# 4. FILTER: 데이터 정제 및 재검색 여부 판단
# ────────────────────────────────────────────
def filter_node(state: Dict[str, Any]):
    print("--- [FILTER] 데이터 정제 중... (qwen3.5:9b) ---")

    raw_candidates = state.get("candidates", [])

    prompt = ChatPromptTemplate.from_template("""
다음 식당 후보 리스트에서 품질 낮은 항목을 걸러내세요.

제거 기준:
- 광고성 콘텐츠
- 평점 4.0 미만
- 이름이 없거나 정보 극히 부족

반드시 아래 JSON 형식으로만 답하세요:
{{
  "filtered_candidates": [
    {{
      "name": "식당이름",
      "score": 4.5,
      "review_count": null,
      "address": null,
      "category": null,
      "price_range": null,
      "source_url": null,
      "summary": "요약"
    }}
  ],
  "needs_retry": false,
  "reason": null
}}

후보 리스트:
{candidates}

결과가 2개 미만이면 needs_retry를 true로 설정하세요.
""")

    chain = prompt | llm_qwen | StrOutputParser()
    raw = chain.invoke({"candidates": str(raw_candidates)})

    fallback = FilterResult(
        filtered_candidates=[Restaurant(**c) for c in raw_candidates[:5]],
        needs_retry=len(raw_candidates) < 2,
    )
    result = parse_structured_output(raw, FilterResult, fallback)

    return {
        "filtered_candidates": [r.model_dump() for r in result.filtered_candidates],
        "needs_retry": result.needs_retry,
        "retry_count": state.get("retry_count", 0) + 1,
    }


# ────────────────────────────────────────────
# 4-1. FILTER 분기 로직 (조건부 엣지용)
# ────────────────────────────────────────────
def filter_logic(state: Dict[str, Any]) -> str:
    needs_retry = state.get("needs_retry", False)
    retry_count = state.get("retry_count", 0)

    if needs_retry and retry_count < 2:
        print(f"--- [FILTER] 결과 부족 → 재검색 (시도 {retry_count}/2) ---")
        return "searcher"
    return "human_approval"


# ────────────────────────────────────────────
# 5. HUMAN APPROVAL: 중단점 징검다리 노드
# ────────────────────────────────────────────
def human_approval(state: Dict[str, Any]):
    print("--- [HUMAN APPROVAL] 사용자 선택 대기 중... ---")
    return state


# ────────────────────────────────────────────
# 6-A. [서브그래프 노드 1] EXTRACTOR: 단일 식당 상세 크롤링
#      Send()로 식당 1개씩 독립 실행 → 병렬 처리
# ────────────────────────────────────────────
def extract_single(state: dict) -> dict:
    """
    단일 식당의 source_url을 Tavily Extract로 크롤링.
    서브그래프 안의 첫 번째 노드.
    """
    restaurant = state.get("restaurant", {})
    name = restaurant.get("name", "알 수 없음")
    url = restaurant.get("source_url")

    print(f"  🔍 [EXTRACTOR] '{name}' 크롤링 중... (exaone3.5:7.8b)")

    if url:
        raw_results = extract_restaurant_detail([url])
        prompt_text = parse_extract_to_prompt(raw_results, name)
    else:
        prompt_text = "URL 없음 - 검색 결과 요약 기반으로만 분석합니다."

    prompt = ChatPromptTemplate.from_template("""
다음 크롤링된 텍스트에서 식당 정보를 추출하세요.
식당 이름: {name}

크롤링 내용:
{raw_text}

반드시 아래 JSON 형식으로만 답하세요:
{{
  "name": "{name}",
  "source_url": "{url}",
  "menu_items": ["메뉴1", "메뉴2"],
  "opening_hours": "영업시간 또는 null",
  "price_range": "가격대 또는 null",
  "highlights": ["특징1", "특징2"],
  "raw_text": null
}}

정보가 없으면 null 또는 빈 배열로 남기세요.
""")

    chain = prompt | llm_exaone | StrOutputParser()
    raw = chain.invoke({
        "name": name,
        "url": url or "",
        "raw_text": prompt_text[:3000],
    })

    fallback = ExtractedDetail(name=name, source_url=url or "")
    result = parse_structured_output(raw, ExtractedDetail, fallback)

    return {
        **state,
        "extracted_detail": result.model_dump(),
    }


# ────────────────────────────────────────────
# 6-B. [서브그래프 노드 2] ANALYST_SINGLE: 단일 식당 분석
#      서브그래프 안의 두 번째 노드.
# ────────────────────────────────────────────
def analyst_single(state: dict) -> dict:
    """
    Extract된 상세 정보 + 검색 요약을 합쳐 단일 식당 인사이트 생성.
    서브그래프의 마지막 노드.
    """
    restaurant = state.get("restaurant", {})
    detail = state.get("extracted_detail", {})
    name = restaurant.get("name", "알 수 없음")

    print(f"  🧠 [ANALYST_SINGLE] '{name}' 분석 중... (exaone3.5:7.8b)")

    prompt = ChatPromptTemplate.from_template("""
다음 식당을 사용자 선호도에 맞게 분석하세요.

사용자 선호도: {preferences}
예산 상한: {max_price}

=== 기본 정보 ===
이름: {name}
평점: {score}
요약: {summary}

=== 크롤링 상세 정보 ===
대표 메뉴: {menu_items}
영업시간: {opening_hours}
가격대: {price_range}
주요 특징: {highlights}

반드시 아래 JSON 형식으로만 답하세요:
{{
  "name": "{name}",
  "pros": ["장점1", "장점2", "장점3"],
  "cons": ["단점1", "단점2"],
  "recommendation_reason": "이 사용자에게 추천하는 이유 한 문장",
  "best_menu": "대표 메뉴명 또는 null"
}}
""")

    chain = prompt | llm_exaone | StrOutputParser()
    raw = chain.invoke({
        "preferences": state.get("preferences", []),
        "max_price": state.get("max_price", "제한 없음"),
        "name": name,
        "score": restaurant.get("score", "N/A"),
        "summary": restaurant.get("summary", ""),
        "menu_items": detail.get("menu_items", []),
        "opening_hours": detail.get("opening_hours", "정보 없음"),
        "price_range": detail.get("price_range", "정보 없음"),
        "highlights": detail.get("highlights", []),
    })

    fallback = RestaurantInsight(
        name=name,
        pros=["정보 부족"],
        cons=[],
        recommendation_reason="추가 정보 확인 필요",
    )
    result = parse_structured_output(raw, RestaurantInsight, fallback)

    return {
        **state,
        "insight": result.model_dump(),
    }


# ────────────────────────────────────────────
# 6-C. COLLECTOR: 병렬 서브그래프 결과 취합 → Writer로 전달
#      Send()로 분산된 결과를 하나의 AnalysisReport로 합침
# ────────────────────────────────────────────
def collector(state: dict) -> dict:
    """
    병렬로 완료된 모든 식당 분석 결과(insights 리스트)를 취합하여
    최종 AnalysisReport를 생성하는 노드.
    """
    print("--- [COLLECTOR] 병렬 분석 결과 취합 중... (gemma4:latest) ---")

    insights = state.get("insights", [])

    if not insights:
        return {
            "analysis_report": {
                "insights": [],
                "top_pick": "분석 결과 없음",
                "summary": "조건에 맞는 식당을 찾지 못했습니다.",
            }
        }

    prompt = ChatPromptTemplate.from_template("""
다음 식당들의 분석 결과를 종합하세요.

분석된 식당들:
{insights}

사용자 선호도: {preferences}

반드시 아래 JSON 형식으로만 답하세요:
{{
  "top_pick": "최종 1순위 식당 이름",
  "summary": "전체 추천 요약 2~3문장"
}}
""")

    class FinalSummary(BaseModel):
        top_pick: str
        summary: str

    chain = prompt | llm_gemma | StrOutputParser()
    raw = chain.invoke({
        "insights": str(insights),
        "preferences": state.get("preferences", []),
    })

    fallback = FinalSummary(
        top_pick=insights[0].get("name", "추천 식당") if insights else "없음",
        summary="분석이 완료되었습니다. 위 식당들을 참고하세요.",
    )
    final = parse_structured_output(raw, FinalSummary, fallback)

    return {
        "analysis_report": {
            "insights": insights,
            "top_pick": final.top_pick,
            "summary": final.summary,
        }
    }


# ────────────────────────────────────────────
# 7. WRITER: 최종 리포트 포맷팅
# ────────────────────────────────────────────
def writer(state: Dict[str, Any]):
    print("--- [WRITER] 최종 답변 작성 중... (gemma4:latest) ---")

    report = state.get("analysis_report", {})
    insights = report.get("insights", [])
    top_pick = report.get("top_pick", "")
    summary = report.get("summary", "")

    # ✅ 구조화된 dict 데이터를 사람이 읽기 좋은 텍스트로 변환
    lines = ["🍽️ AI 맛집 추천 리포트", "=" * 40, ""]

    for idx, insight in enumerate(insights, 1):
        lines.append(f"[{idx}위] {insight.get('name', '')}")
        if insight.get("best_menu"):
            lines.append(f"  🍜 대표 메뉴: {insight['best_menu']}")
        lines.append(f"  ✅ 장점: {', '.join(insight.get('pros', []))}")
        lines.append(f"  ⚠️  단점: {', '.join(insight.get('cons', []))}")
        lines.append(f"  💬 추천 이유: {insight.get('recommendation_reason', '')}")
        lines.append("")

    lines.append("=" * 40)
    lines.append(f"🏆 최종 픽: {top_pick}")
    lines.append(f"📝 요약: {summary}")

    return {"final_answer": "\n".join(lines)}