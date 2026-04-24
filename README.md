# 🍽️ AI 맛집 큐레이터

> LangGraph 기반 멀티 에이전트 맛집 추천 시스템

사용자의 자연어 요청을 분석하여 실시간으로 맛집 데이터를 수집하고, 여러 AI 에이전트가 협업하여 최적의 장소를 추천하는 **풀스택 지능형 시스템**입니다.  
단순 목록 나열이 아닌, **데이터 필터링 → 사용자 개입(HITL) → 심층 분석 → 리포트 생성**의 정교한 워크플로우를 통해 실제 사람이 추천하는 듯한 경험을 제공합니다.

---

## 🌟 주요 특징

| 기능 | 설명 |
|---|---|
| **Multi-Agent Orchestration** | LangGraph로 구성된 7개 독립 노드(Manager~Writer)가 순차·병렬 협업 |
| **Intelligent Routing** | 질문 의도를 파악해 검색 필요 여부를 동적으로 분기 |
| **Self-Correction Loop** | 검색 결과 부족 시 Filter 노드가 자동 재검색 (최대 2회) |
| **Human-in-the-Loop (HITL)** | 최종 분석 전 사용자가 후보 식당을 직접 선택하는 중단점 구현 |
| **병렬 서브그래프** | 선택된 식당들을 `Send() API`로 동시에 분석해 응답 속도 최적화 |
| **SSE 실시간 스트리밍** | 각 에이전트 노드 완료 시 진행 상황을 프론트엔드에 실시간 전송 |
| **북마크 / 공유** | 마음에 드는 식당 북마크 저장 및 결과 페이지 URL 공유 기능 |

---

## 🏗️ 시스템 아키텍처

```
사용자 입력
    │
    ▼
┌─────────┐     파라미터 추출 (위치, 카테고리, 예산)
│ Manager │  ◄── qwen3.5:9b
└────┬────┘
     │ router_logic
     ▼
┌──────────┐     Tavily Search API로 실시간 맛집 수집
│ Searcher │
└────┬─────┘
     │
     ▼
┌────────┐      평점·신뢰도 필터링 / 결과 부족 시 재검색  ◄──┐
│ Filter │  ◄── qwen3.5:9b                                   │
└────┬───┘                                                    │
     │ needs_retry=true                                        │
     └──────────────────────────────────────────────────────── ┘
     │ needs_retry=false
     ▼
┌────────────────┐    [INTERRUPT] 사용자가 분석할 식당 선택
│ Human Approval │  ◄── LangGraph Command API
└───────┬────────┘
        │ approve / modify
        ▼
┌──────────┐    Send() → 선택 식당 병렬 처리
│ Dispatch │
└──────────┘
     │          ┌─────────────────────────────────────┐
     ├──────────► Extractor  (exaone3.5:7.8b) │ 식당 1 │
     ├──────────► Extractor  (exaone3.5:7.8b) │ 식당 2 │  병렬
     └──────────► Extractor  (exaone3.5:7.8b) │ 식당 N │
                 └──────────────────────────────────────┘
                             │ Analyst_Single
                             ▼
                    ┌──────────────┐   결과 종합
                    │  Collector   │  ◄── gemma4:latest
                    └──────┬───────┘
                           │
                           ▼
                    ┌────────┐   최종 추천 리포트 생성
                    │ Writer │  ◄── gemma4:latest
                    └────────┘
```

---

## 📂 프로젝트 구조

```
restaurant_recommandation/
│
├── 📄 main.py              # FastAPI 앱 진입점, Ollama 연결 확인
├── 📄 graph.py             # LangGraph 워크플로우 · 상태(AgentState) 정의
├── 📄 agents.py            # 7개 에이전트 노드 LLM 로직
├── 📄 tools.py             # Tavily Search / Extract API 통신
├── 📄 chat.py              # SSE 스트리밍 엔드포인트 · 북마크 · 공유 API
├── 📄 schemas.py           # Pydantic 데이터 모델
├── 📄 langgraph.json       # LangGraph Studio 설정
├── 📄 requirements.txt
├── 📁 data/
│   ├── checkpoints.db      # SQLite 세션 체크포인트
│   ├── bookmarks.json      # 북마크 저장소
│   └── shares.json         # 공유 링크 저장소
│
└── 📁 frontend/            # React + Vite 프론트엔드
    ├── 📄 package.json
    ├── 📄 vite.config.js
    ├── 📄 index.html
    └── 📁 src/
        ├── 📄 main.jsx
        ├── 📄 App.jsx
        ├── 📄 index.css
        ├── 📄 api.js        # 백엔드 API 호출 모듈
        ├── 📁 pages/
        │   ├── ChatPage.jsx  # 메인 검색·추천 페이지
        │   └── SharePage.jsx # 공유 결과 조회 페이지
        └── 📁 components/
            ├── RestaurantCard.jsx  # 식당 카드 컴포넌트
            └── KakaoMap.jsx        # 카카오맵 연동 컴포넌트
```

---

## 🛠️ 기술 스택

### Backend
| 항목 | 내용 |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI · Uvicorn |
| AI Orchestration | LangGraph 0.2+ · LangChain 0.3+ |
| LLM | Ollama 로컬 모델 (qwen3.5:9b · exaone3.5:7.8b · gemma4) |
| Search | Tavily Search API · Tavily Extract |
| Persistence | SQLite (LangGraph Checkpoint) · JSON 파일 |
| Streaming | SSE (Server-Sent Events) |

### Frontend
| 항목 | 내용 |
|---|---|
| Framework | React 18 · Vite 5 |
| Routing | React Router v6 |
| Styling | styled-components |
| Map | 카카오맵 JavaScript API |

---

## 🚀 시작하기

### 사전 요구 사항

- Python 3.12+
- Node.js 18+
- [Ollama](https://ollama.com) 설치 및 실행

### 1. Ollama 모델 다운로드

```bash
ollama pull qwen3.5:9b
ollama pull exaone3.5:7.8b
ollama pull gemma4:latest
```

### 2. 백엔드 설정

```bash
# 저장소 클론 후 프로젝트 폴더 이동
cd restaurant_recommandation

# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 패키지 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 입력합니다:

```env
TAVILY_API_KEY=your_tavily_api_key
LANGSMITH_API_KEY=your_langsmith_api_key   # 선택
LANGSMITH_TRACING=false
OLLAMA_BASE_URL=http://localhost:11434
```

> Tavily API 키 발급: https://tavily.com

### 4. 프론트엔드 설정

```bash
cd frontend

# 환경 변수 파일 생성
copy .env.example .env
# .env 파일을 열고 VITE_KAKAO_MAP_KEY에 카카오 JavaScript 키 입력

# 패키지 설치
npm install
```

### 5. 실행

터미널 두 개를 열어 각각 실행합니다.

**터미널 1 — 백엔드**
```bash
# 프로젝트 루트에서
ollama serve   # Ollama가 실행 중이 아닌 경우

uvicorn main:app --reload --port 8000
```

**터미널 2 — 프론트엔드**
```bash
cd frontend
npm run dev
```

브라우저에서 **http://localhost:5173** 접속

---

## 📡 API 엔드포인트

| Method | Endpoint | 설명 |
|---|---|---|
| `GET` | `/api/chat/start/stream` | 검색 시작 및 SSE 스트리밍 |
| `GET` | `/api/chat/select/stream` | 식당 선택 후 분석 SSE 스트리밍 |
| `POST` | `/api/chat/reject` | 결과 거절 및 재검색 |
| `POST` | `/api/chat/bookmark` | 북마크 추가 |
| `GET` | `/api/chat/bookmarks` | 북마크 목록 조회 |
| `POST` | `/api/chat/share` | 공유 링크 생성 |
| `GET` | `/api/chat/share/{code}` | 공유 결과 조회 |
| `GET` | `/health` | 서버 상태 확인 |
| `GET` | `/docs` | Swagger API 문서 |

---

## 🔄 실행 흐름 예시

```
사용자: "홍대 근처 분위기 좋은 파스타 맛집 알려줘"

1. Manager  → location="홍대", category="파스타" 추출
2. Searcher → Tavily로 실시간 맛집 10개 수집
3. Filter   → 평점 4.0 미만 · 광고성 제거 → 5개 필터링
4. [중단]   → 사용자에게 5개 후보 카드 표시
5. 사용자   → "파스타 하우스", "라 루나" 2곳 선택
6. Dispatch → 2곳 병렬 분석 시작
7. Extractor→ 각 식당 URL 크롤링 → 메뉴·가격·특징 추출
8. Analyst  → 선호도·예산 기반 장단점 분석
9. Collector→ 2곳 결과 종합, 1순위 결정
10. Writer  → 최종 추천 리포트 작성 및 표시
```

---

## 💡 기술적 인사이트

**LangGraph Command API + HITL**  
`interrupt()` + `Command(goto=..., update=...)` 조합으로 그래프 실행을 중단하고 사용자 입력을 받은 뒤 원하는 노드로 재개하는 패턴을 구현했습니다. Checkpoint를 SQLite에 저장하여 서버 재시작 후에도 세션이 유지됩니다.

**병렬 서브그래프 (`Send()` API)**  
사용자가 N개의 식당을 선택하면 `Send()` API로 각 식당을 독립 서브그래프에 동시 투입합니다. `Annotated[List, operator.add]` 타입으로 병렬 결과를 자동 누적해 순서와 관계없이 올바르게 집계됩니다.

**로컬 LLM 역할 분담**  
단일 모델 대신 역할에 따라 3개 로컬 모델을 분산 배치했습니다.  
- `qwen3.5:9b` → 한국어 NER (파라미터 추출, 필터링 판단)  
- `exaone3.5:7.8b` → 긴 문서 분석 (크롤링 텍스트 이해, 인사이트 추출)  
- `gemma4` → 자연스러운 문장 생성 (종합 요약, 리포트 작성)

**SSE 실시간 스트리밍**  
`astream_events(version="v2")`로 노드 완료 이벤트를 감지하고 `text/event-stream` 형식으로 프론트엔드에 즉시 전달합니다. 사용자는 분석이 진행되는 동안 각 단계 완료 현황을 실시간으로 확인할 수 있습니다.
