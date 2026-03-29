from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from typing import Dict, Any
from tools.search_api import get_restaurant_search_tool
# 공통 LLM 설정
llm_model = "gpt-4o-mini" # 분석용은 mini, 복잡한 판단은 gpt-4o 권장

# 1. MANAGER: 질문 분석 및 파라미터 추출
def manager(state: Dict[str, Any]):
    print("--- [MANAGER] 질문 분석 중... ---")
    llm = ChatOpenAI(model=llm_model, temperature=0)
    
    prompt = ChatPromptTemplate.from_template("""
    당신은 맛집 추천 팀의 매니저입니다. 사용자의 질문에서 다음 정보를 추출하여 JSON으로 답변하세요.
    - location: 지역 (예: 강남역, 홍대)
    - category: 음식 종류 (예: 일식, 삼겹살, 카페)
    - preferences: 분위기나 특징 리스트 (예: ["조용한", "주차가능"])
    
    질문: {query}
    """)
    
    chain = prompt | llm | JsonOutputParser()
    result = chain.invoke({"query": state["query"]})
    
    # 추출된 정보를 state에 업데이트
    return {
        "location": result.get("location"),
        "category": result.get("category"),
        "preferences": result.get("preferences")
    }

# 2. ROUTER: 실행 경로 결정 (조건부 엣지용 함수)
def router(state: Dict[str, Any]):
    print("--- [ROUTER] 경로 판단 중... ---")
    # 단순 로직 처리 혹은 LLM 사용 가능
    if state.get("location") and state.get("category"):
        return "searcher"  # 검색으로 이동
    return "analyst"       # 정보가 충분하면 바로 분석 (혹은 에러 처리)

# 3. SEARCHER: 데이터 수집 (Tool 호출)
from tools.search_api import * # 도구 임포트

def searcher(state: Dict[str, Any]):
    print(f"--- [TAVILY SEARCHER] {state['location']} 맛집 정밀 검색 중... ---")
    
    search_tool = get_restaurant_search_tool()
    
    # 질의를 더 구체화하여 평점과 리뷰를 유도합니다.
    query = f"{state['location']} {state['category']} 맛집 평점 및 리뷰 요약"
    
    # Tavily 실행
    search_results = search_tool.invoke({"query": query})
    
    # search_results에는 각 사이트의 URL과 본문 요약(content)이 들어있습니다.
    return {"candidates": search_results}

# 4. FILTER: 데이터 정제 및 품질 검사
def filter(state: Dict[str, Any]):
    print("--- [FILTER] 데이터 정제 중... ---")
    candidates = state.get("candidates", [])
    
    # 예: 평점 기반 필터링이나 중복 제거 로직 (여기서는 단순 전달)
    filtered = [c for c in candidates if "광고" not in c.get("title", "")]
    
    return {"filtered_candidates": filtered}

# 5. ANALYST: 리뷰 심층 분석
def analyst(state: Dict[str, Any]):
    print("--- [ANALYST] Tavily를 통한 리뷰 분석 및 요약 중... ---")
    llm = ChatOpenAI(model="gpt-4o", temperature=0.5) # 창의적 요약을 위해 gpt-4o 사용
    
    # 사용자가 선택한 식당 정보만 추출
    selected_indices = state.get("selected_indices", [0]) # 선택 없으면 첫 번째
    targets = [state["filtered_candidates"][i] for i in selected_indices]
    
    prompt = ChatPromptTemplate.from_template("""
    다음 식당들에 대한 상세 정보를 바탕으로 사용자 맞춤형 추천 리포트를 작성하세요.
    사용자 선호도: {preferences}
    대상 식당: {targets}
    
    각 식당의 특징, 장점, 그리고 왜 사용자에게 적합한지 상세히 설명하세요.
    """)
    
    chain = prompt | llm | StrOutputParser()
    report = chain.invoke({"preferences": state["preferences"], "targets": targets})
    
    return {"analysis_report": report}

# 6. WRITER: 최종 답변 다듬기
def writer(state: Dict[str, Any]):
    print("--- [WRITER] 최종 답변 작성 중... ---")
    # Analyst의 결과를 그대로 쓰거나, 말투를 다듬음
    final_answer = f"🏠 요청하신 맛집 분석 결과입니다.\n\n{state['analysis_report']}"
    return {"final_answer": final_answer}