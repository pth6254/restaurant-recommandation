"""
schemas.py
----------
프로젝트 전체에서 사용하는 Pydantic 데이터 모델 정의.
LLM의 structured output 및 State 타입 검증에 활용합니다.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ────────────────────────────────────────────
# 1. Manager 노드 출력 스키마
#    - LLM이 사용자 질문에서 추출할 파라미터
# ────────────────────────────────────────────
class QueryParams(BaseModel):
    """Manager 노드: 사용자 질문 파싱 결과"""
    location: str = Field(description="검색할 지역명. 예: 강남역, 홍대입구")
    category: str = Field(description="음식 카테고리. 예: 일식, 삼겹살, 카페")
    preferences: List[str] = Field(
        default_factory=list,
        description="분위기·특징 키워드 리스트. 예: ['조용한', '주차가능', '가성비']"
    )
    max_price: Optional[int] = Field(
        default=None,
        description="1인 기준 최대 예산(원). 언급 없으면 None"
    )


# ────────────────────────────────────────────
# 2. 개별 식당 후보 스키마
#    - Searcher/Filter 노드가 다루는 단위 데이터
# ────────────────────────────────────────────
class Restaurant(BaseModel):
    """식당 후보 한 건"""
    name: str = Field(description="식당 이름")
    score: float = Field(default=0.0, description="평점 (0.0 ~ 5.0)")
    review_count: Optional[int] = Field(default=None, description="리뷰 수")
    address: Optional[str] = Field(default=None, description="주소")
    category: Optional[str] = Field(default=None, description="음식 카테고리")
    price_range: Optional[str] = Field(default=None, description="가격대. 예: 1만~2만원")
    source_url: Optional[str] = Field(default=None, description="출처 URL")
    summary: Optional[str] = Field(default=None, description="리뷰 요약")


# ────────────────────────────────────────────
# 3. Filter 노드 출력 스키마
# ────────────────────────────────────────────
class FilterResult(BaseModel):
    """Filter 노드: 정제 결과 및 재검색 여부"""
    filtered_candidates: List[Restaurant] = Field(
        description="필터링을 통과한 식당 리스트"
    )
    needs_retry: bool = Field(
        default=False,
        description="결과가 부족하여 재검색이 필요한 경우 True"
    )
    reason: Optional[str] = Field(
        default=None,
        description="재검색이 필요한 이유 (디버깅용)"
    )


# ────────────────────────────────────────────
# 4. Analyst 노드 출력 스키마
# ────────────────────────────────────────────
class RestaurantInsight(BaseModel):
    """식당 한 곳에 대한 분석 인사이트"""
    name: str = Field(description="식당 이름")
    pros: List[str] = Field(description="장점 리스트")
    cons: List[str] = Field(description="단점 또는 주의사항 리스트")
    recommendation_reason: str = Field(
        description="이 사용자에게 추천하는 이유 (한 문장)"
    )
    best_menu: Optional[str] = Field(default=None, description="대표 메뉴")


class AnalysisReport(BaseModel):
    """Analyst 노드: 전체 분석 결과"""
    insights: List[RestaurantInsight] = Field(description="식당별 인사이트 리스트")
    top_pick: str = Field(description="최종 1순위 추천 식당 이름")
    summary: str = Field(description="전체 추천 요약 (2~3문장)")
