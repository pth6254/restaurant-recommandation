"""
tools.py
--------
외부 API 통신 담당 (Tavily Search / Extract).
"""

import os
import json
import asyncio
import httpx
import urllib.parse
import urllib.request
import urllib.error
from typing import List
from langchain_tavily import TavilySearch
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv

load_dotenv()


_tavily_search = TavilySearch(max_results=10, search_depth="advanced")


def _normalize_tavily(input_dict: dict) -> list:
    result = _tavily_search.invoke(input_dict)
    if isinstance(result, dict):
        return result.get("results", [])
    if isinstance(result, list):
        return result
    return []


RESTAURANT_SEARCH_TOOL = RunnableLambda(_normalize_tavily)


async def extract_restaurant_detail(urls: List[str]) -> List[dict]:
    """Tavily Extract로 식당 URL 본문 비동기 크롤링. 실패 시 빈 리스트 반환."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []

    valid_urls = [u for u in urls if u and u.startswith("http")]
    if not valid_urls:
        return []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.tavily.com/extract",
                json={"api_key": api_key, "urls": valid_urls[:20]},
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
            results.append({"url": item.get("url", ""), "raw_content": "", "failed": True})

        return results

    except httpx.TimeoutException:
        print("  ⚠️ Tavily Extract 타임아웃")
        return []
    except Exception as e:
        print(f"  ⚠️ Tavily Extract 오류: {e}")
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


async def search_restaurants_kakao(location: str, category: str, size: int = 15) -> List[dict]:
    """카카오 로컬 API 키워드 검색으로 식당 목록 수집.
    반환: place_name, address, category, source_url, x(경도), y(위도) 포함 dict 리스트.
    KAKAO_REST_API_KEY 미설정 시 빈 리스트 반환.
    """
    api_key = os.getenv("KAKAO_REST_API_KEY")
    if not api_key:
        return []

    try:
        # urllib.parse.quote로 percent-encoding 후 urllib.request로 직접 요청.
        # httpx는 URL을 내부 파싱하면서 percent-encoding을 풀어 ASCII 인코딩 오류를 유발함.
        query_enc = urllib.parse.quote(f"{location} {category}", safe="", encoding="utf-8")
        url = (
            f"https://dapi.kakao.com/v2/local/search/keyword.json"
            f"?query={query_enc}&category_group_code=FD6&size={size}"
        )
        req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {api_key}"})

        def _fetch():
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))

        data = await asyncio.to_thread(_fetch)
        docs = data.get("documents", [])

        return [
            {
                "name":       doc.get("place_name", ""),
                "address":    doc.get("road_address_name") or doc.get("address_name", ""),
                "category":   doc.get("category_name", "").split(" > ")[-1],
                "source_url": doc.get("place_url", ""),
                "x":          doc.get("x", ""),
                "y":          doc.get("y", ""),
                "phone":      doc.get("phone", ""),
            }
            for doc in docs
            if doc.get("place_name")
        ]

    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, "reason") else str(e)
        if "timed out" in reason.lower():
            print("  ⚠️ 카카오 로컬 API 타임아웃")
        else:
            print(f"  ⚠️ 카카오 로컬 API 오류: {e}")
        return []
    except Exception as e:
        print(f"  ⚠️ 카카오 로컬 API 오류: {e}")
        return []


async def search_restaurant_reviews(restaurant_name: str, location: str = "") -> str:
    """특정 식당의 리뷰를 Tavily로 검색. 내용 텍스트 반환."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return ""

    query = f"{location} {restaurant_name} 리뷰 후기".strip()
    _tool = TavilySearch(max_results=3, search_depth="basic")
    try:
        result = await _tool.ainvoke({"query": query})
        results = result.get("results", []) if isinstance(result, dict) else result
        texts = [r.get("content", "") for r in results[:3] if r.get("content")]
        return "\n\n".join(texts)[:2000]
    except Exception:
        return ""
