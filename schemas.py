"""
schemas.py
----------
프로젝트 전체에서 사용하는 Pydantic 데이터 모델 정의.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class QueryParams(BaseModel):
    location: str = Field(description="검색할 지역명. 예: 강남역")
    category: str = Field(description="음식 카테고리. 예: 일식")
    preferences: List[str] = Field(default_factory=list)
    max_price: Optional[int] = Field(default=None)


class Restaurant(BaseModel):
    name: str
    score: float = Field(default=0.0)
    review_count: Optional[int] = None
    address: Optional[str] = None
    category: Optional[str] = None
    price_range: Optional[str] = None
    source_url: Optional[str] = None
    summary: Optional[str] = None
    x: Optional[str] = None  # 경도 (카카오 로컬 API)
    y: Optional[str] = None  # 위도 (카카오 로컬 API)


class FilterResult(BaseModel):
    filtered_candidates: List[Restaurant]
    needs_retry: bool = False
    reason: Optional[str] = None


class RestaurantInsight(BaseModel):
    name: str
    pros: List[str]
    cons: List[str]
    recommendation_reason: str
    best_menu: Optional[str] = None


class AnalysisReport(BaseModel):
    insights: List[RestaurantInsight]
    top_pick: str
    summary: str


class ExtractedDetail(BaseModel):
    name: str
    source_url: str = ""
    menu_items: List[str] = Field(default_factory=list)
    opening_hours: Optional[str] = None
    price_range: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


class FinalSummary(BaseModel):
    top_pick: str
    summary: str


class HitlAction(BaseModel):
    """
    HITL 중단점 사용자 응답 스키마.
      approve : 선택한 식당으로 분석 진행
      reject  : 전체 거절 → 재검색
      modify  : 선택 번호 수정 후 진행
    """
    action: Literal["approve", "reject", "modify"]
    selected_indices: List[int] = Field(default_factory=list)
    feedback: Optional[str] = None