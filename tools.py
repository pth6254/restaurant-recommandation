"""
tools.py
--------
외부 API 통신 담당 (Tavily Search / Extract).
"""

import os
import requests
from typing import List
from langchain_tavily import TavilySearch
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv

load_dotenv()


def get_restaurant_search_tool() -> RunnableLambda:
    """식당 후보 목록 검색용 Tavily Search 도구. 결과를 list[dict]로 정규화."""
    _tool = TavilySearch(max_results=10, search_depth="advanced")

    def _normalize(input_dict: dict) -> list:
        result = _tool.invoke(input_dict)
        if isinstance(result, dict):
            return result.get("results", [])
        if isinstance(result, list):
            return result
        return []

    return RunnableLambda(_normalize)


RESTAURANT_SEARCH_TOOL: RunnableLambda = get_restaurant_search_tool()


def extract_restaurant_detail(urls: List[str]) -> List[dict]:
    """Tavily Extract로 식당 URL 본문 직접 크롤링. 실패 시 빈 리스트 반환."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
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
            results.append({"url": item.get("url", ""), "raw_content": "", "failed": True})

        return results

    except requests.exceptions.Timeout:
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
