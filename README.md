# 🍽️ AI 맛집 큐레이션 멀티 에이전트 (LangGraph 기반)

사용자의 모호한 맛집 요청을 분석하여 실시간 데이터를 수집하고, 여러 AI 에이전트가 협업하여 최적의 장소를 추천하는 **지능형 멀티 에이전트 시스템**입니다. 
단순히 목록을 나열하는 기존 봇과 달리, **데이터 필터링, 재검색 루프, 그리고 사용자 개입(Human-in-the-Loop)** 과정을 통해 실제 사람이 추천하는 듯한 정교한 워크플로우를 제공합니다.

---

## 🌟 주요 특징 (Key Features)

* **Multi-Agent Orchestration**: LangGraph를 활용하여 Manager, Router, Searcher 등 7개의 독립 노드가 협업하는 구조 설계.
* **Intelligent Routing**: 질문의 의도(단순 추천 vs 상세 정보 문의)를 파악하여 최적의 경로로 동적 분기.
* **Self-Correction Loop**: 검색 결과가 부실할 경우 Filter 노드에서 스스로 판단하여 다시 Searcher로 돌아가는 재검색 로직 구현.
* **Human-in-the-Loop (HITL)**: 최종 분석 전 사용자가 후보지 중 원하는 곳을 직접 선택할 수 있는 중단점(Interrupt) 및 상태 저장(Checkpoint) 기능 활용.

---

## 🏗️ 시스템 아키텍처 (Workflow)

본 프로젝트는 다음과 같은 에이전트 흐름을 가집니다.

[Image of a professional multi-agent system flowchart with nodes: Manager, Router, Searcher, Filter, Human-Approval, Analyst, Writer]

1.  **Manager**: 사용자 질문에서 위치, 카테고리, 예산 등 핵심 파라미터 추출.
2.  **Router**: 신규 검색이 필요한지, 기존 정보로 답변 가능한지 판단하여 경로 배분.
3.  **Searcher**: Naver/Google Local API를 통해 실시간 맛집 데이터 수집.
4.  **Filter**: 평점 및 리뷰 신뢰도를 검증하고 결과 부족 시 재검색 루프 실행.
5.  **Human Approval (HITL)**: **[중단점]** 사용자가 분석을 진행할 식당을 직접 선택.
6.  **Analyst**: 선택된 식당의 블로그 및 방문자 리뷰를 심층 분석하여 인사이트 추출.
7.  **Writer**: 분석 내용을 바탕으로 최종 추천 리포트 작성.

---

## 📂 프로젝트 구조 (Directory Structure)

```text
.
├── main.py              # 애플리케이션 진입점 및 HITL 제어 로직
├── graph.py             # LangGraph 워크플로우 및 상태(State) 정의
├── agents/
│   └──agents.py            # 각 에이전트(Node)의 LLM 프롬프트 및 행동 정의
├── tools/               # 외부 연동 도구 모음
│   └── search_api.py    # 네이버/구글 검색 API 호출 함수
├── langgraph.json       # LangGraph Studio 시각화 및 배포 설정
└── .env                 # API Keys (OpenAI, Naver 등) 관리
```


## ⚡ 상세 프로젝트 구조 (Project Structure)

프로젝트는 관심사의 분리(SoC) 원칙에 따라 계층별로 설계되었습니다.

### 1. 🚀 실행 제어 계층 (Execution)
- **`main.py`**: 애플리케이션의 엔트리 포인트입니다. 사용자 입력을 받고, `thread_id` 기반의 세션 관리 및 HITL(중단점 재개) 컨트롤러 역할을 수행합니다.

### 2. 🗺️ 워크플로우 설계 계층 (Orchestration)
- **`graph.py`**: 시스템의 '설계도'입니다. `TypedDict` 기반의 `AgentState` 정의, 노드 등록, 조건부 분기(Conditional Edges) 및 지속성(Persistence) 설정을 담당합니다.

### 3. 🧠 지능형 에이전트 계층 (Agent)
- **`agents.py`**: 각 단계별 특화된 LLM 로직을 포함합니다.
    - **Manager**: 자연어에서 파라미터를 추출하는 NER 수행.
    - **Router/Filter**: 논리적 판단을 통해 실행 경로 및 데이터 품질 결정.
    - **Analyst/Writer**: 비정형 데이터 분석 및 사용자 맞춤형 리포트 생성.

### 4. 🛠️ 외부 도구 계층 (Tool)
- **`tools/search_api.py`**: 외부 API(Naver)와의 통신을 담당합니다. 데이터 수집 및 에이전트가 읽기 좋은 형태로 전처리(Data Cleaning)를 수행합니다.
- **`tools/__init__.py`**: 도구 함수들을 패키지화하여 외부에서 간결하게 호출할 수 있는 인터페이스를 제공합니다.

---

## 🛠️ 기술 스택 (Tech Stack)
- Framework: LangChain, LangGraph
- LLM: OpenAI GPT-4o, GPT-4o-mini
- Language: Python 3.12.10
- Infrastructure: LangGraph Studio (Visualization & Debugging)
- Persistence: MemorySaver (State Checkpointing)

---

## 🚀 시작하기 (Getting Started)
1. 환경 변수 설정: .env 파일을 생성하고 키를 입력합니다.
OPENAI_API_KEY=your_openai_api_key
NAVER_CLIENT_ID=your_naver_id
NAVER_CLIENT_SECRET=your_naver_secret
2. 필수 라이브러리 설치:
pip install -U langchain-openai langgraph requests python-dotenv
3. 프로그램 실행: python main.py

---

## 💡 인사이트 및 배운 점
**상태 관리(State Management)**: TypedDict를 활용하여 복잡한 에이전트 간 데이터 전달 규격을 표준화함.
**에이전트 독립성**: 각 기능을 노드로 분리하여 특정 단계(예: 필터링 로직)의 성능을 개별적으로 개선할 수 있는 확장성 확보.
**인간-AI 협업**: 모든 과정을 자동화하는 것보다 중요한 결정 단계(식당 선택)에 사람의 개입을 허용함으로써 결과물의 신뢰도와 사용자 만족도를 동시에 높임.