
import os
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()

def get_restaurant_search_tool():
    # k=10: 상위 10개 검색 결과 리턴
    # search_depth="advanced": 더 깊은 분석(리뷰, 평점 등)을 위해 고성능 검색 사용
    return TavilySearchResults(k=10, search_depth="advanced")