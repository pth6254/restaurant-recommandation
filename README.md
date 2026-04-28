# 🍽️ AI 맛집 큐레이터

> LangGraph 기반 멀티 에이전트 맛집 추천 시스템

사용자의 자연어 요청을 분석하여 실시간으로 맛집 데이터를 수집하고, 여러 AI 에이전트가 협업하여 최적의 장소를 추천하는 **풀스택 지능형 시스템**입니다.  
단순 목록 나열이 아닌, **데이터 필터링 → 사용자 개입(HITL) → 심층 분석 → 리포트 생성**의 정교한 워크플로우를 통해 실제 사람이 추천하는 듯한 경험을 제공합니다.

---

## 🌟 주요 특징

| 기능 | 설명 |
|---|---|
| **Multi-Agent Orchestration** | LangGraph로 구성된 7개 독립 노드(Manager~Writer)가 순차·병렬 협업 |
| **이중 검색 전략** | 카카오 로컬 API(정확한 위치·좌표)와 Tavily Search API(웹 리뷰)를 결합 |
| **Intelligent Routing** | 질문 의도를 파악해 검색 필요 여부를 동적으로 분기 |
| **Self-Correction Loop** | 검색 결과 부족 시 Filter 노드가 자동 재검색 (최대 2회) |
| **Human-in-the-Loop (HITL)** | 최종 분석 전 사용자가 후보 식당을 직접 선택하는 중단점 구현 |
| **병렬 서브그래프** | 선택된 식당들을 `Send() API`로 동시에 분석해 응답 속도 최적화 |
| **SSE 실시간 스트리밍** | 각 에이전트 노드 완료 시 진행 상황을 프론트엔드에 실시간 전송 |
| **카카오맵 시각화** | 추천 식당 위치를 카카오맵 마커로 표시 |
| **북마크 / 공유** | 마음에 드는 식당 북마크 저장 및 결과 페이지 URL 공유 기능 |

---

## 🏗️ 시스템 아키텍처

```
사용자 입력
    │
    ▼
┌─────────┐     파라미터 추출 (위치, 카테고리, 예산, 선호도)
│ Manager │  ◄── qwen3.5:9b
└────┬────┘
     │ router_logic: 검색 필요 여부 판단
     ▼
┌──────────┐     1차: 카카오 로컬 API (좌표·공식 정보)
│ Searcher │     2차: Tavily Search API (웹 리뷰 · 폴백)
└────┬─────┘     → LLM 배치로 식당명·요약 정제
     │
     ▼
┌────────┐      리스트성 블로그 제거 · 짧은 콘텐츠 필터링  ◄──┐
│ Filter │  ◄── Python 정규식 (LLM 미사용)                    │
└────┬───┘  후보 2개 미만 시 needs_retry=true                  │
     │ needs_retry=true ──────────────────────────────────────┘
     │ needs_retry=false
     ▼
┌────────────────┐    [INTERRUPT] 사용자가 분석할 식당 선택
│ Human Approval │  ◄── LangGraph Command API + interrupt()
└───────┬────────┘    approve / modify / reject(재검색)
        │
        ▼
┌──────────┐    Send() → 선택 식당 독립 서브그래프 병렬 투입
│ Dispatch │
└──────────┘
         ┌─────────────────────────────────────────────┐
         ├──► Extractor → Analyst  (식당 1)  ─────────┤
         ├──► Extractor → Analyst  (식당 2)  ─────────┤  병렬
         └──► Extractor → Analyst  (식당 N)  ─────────┤
              exaone3.5:7.8b                           │
                                                       ▼
                                              ┌──────────────┐
                                              │  Collector   │  결과 종합 · 1순위 결정
                                              └──────┬───────┘  gemma4:latest
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
├── 📄 graph.py             # LangGraph 워크플로우 · AgentState 정의
├── 📄 agents.py            # 7개 에이전트 노드 구현
├── 📄 tools.py             # Kakao Local API · Tavily API 통신
├── 📄 chat.py              # SSE 스트리밍 · 북마크 · 공유 API 라우터
├── 📄 schemas.py           # Pydantic 데이터 모델
├── 📄 app_state.py         # 전역 LangGraph 앱 인스턴스
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
        ├── 📄 api.js           # 백엔드 API 호출 모듈
        ├── 📁 pages/
        │   ├── ChatPage.jsx    # 메인 검색·추천 페이지
        │   └── SharePage.jsx   # 공유 결과 조회 페이지
        └── 📁 components/
            ├── RestaurantCard.jsx  # 식당 카드 컴포넌트
            └── KakaoMap.jsx        # 카카오맵 연동 컴포넌트
```

---

## ⚙️ 구현된 기능 상세

### 1. 에이전트 노드 (agents.py)

| 노드 | 모델 | 입력 | 출력 |
|---|---|---|---|
| `manager` | qwen3.5:9b | 자연어 쿼리 | location, category, preferences, max_price |
| `router_logic` | 로직 | location, category | `"searcher"` \| `"analyst"` |
| `searcher` | 카카오/Tavily API (Tavily 폴백 시 qwen3.5:9b로 식당명 정제) | 검색 파라미터 | candidates 목록 |
| `filter_node` | Python 정규식 | candidates | filtered_candidates, needs_retry |
| `filter_logic` | 로직 | needs_retry, retry_count | `"searcher"` \| `"human_approval"` |
| `human_approval` | interrupt() | filtered_candidates | Command(goto, update) |
| `dispatch` | Send() API | selected_indices | 병렬 서브그래프 투입 |
| `extract_single` | exaone3.5:7.8b | restaurant URL | menu_items, hours, price_range |
| `analyst_single` | exaone3.5:7.8b | extracted_detail | pros, cons, recommendation_reason |
| `collector` | gemma4 | insights[] | analysis_report, top_pick |
| `writer` | gemma4 | analysis_report | final_answer (마크다운 리포트) |

### 2. 검색 도구 (tools.py)

- **`search_restaurants_kakao()`** — 카카오 로컬 API (`category_group_code=FD6`)로 음식점 검색. 공식 식당명, 주소, 좌표(x/y), 카카오맵 URL 반환
- **`RESTAURANT_SEARCH_TOOL`** — Tavily Search 래퍼 (max_results=10). 카카오 API 폴백용
- **`extract_restaurant_detail()`** — Tavily Extract로 URL 크롤링, 메뉴·영업시간·특징 추출 (async)
- **`search_restaurant_reviews()`** — 카카오맵 URL 대응 Tavily 리뷰 검색 폴백
- **`parse_extract_to_prompt()`** — 크롤링 결과를 LLM 입력용 텍스트로 포맷팅

### 3. HITL (Human-in-the-Loop)

- `interrupt()` 호출 시 필터링된 후보 5~8개를 프론트엔드에 전달하고 그래프 실행 일시 중단
- 사용자 액션 3종:
  - **approve** — 선택한 식당 그대로 분석 진행
  - **modify** — 선택 변경 후 분석 진행
  - **reject** — 전체 거절, 피드백과 함께 재검색 (`goto="searcher"`)
- 세션 상태는 SQLite 체크포인트에 저장 → 서버 재시작 후에도 thread_id로 복원 가능

### 4. 병렬 처리 (Send() API)

- `dispatch` 노드에서 선택된 N개 식당 각각을 `Send()` API로 독립 서브그래프에 투입
- `AgentState.insights` 필드를 `Annotated[List, operator.add]`로 정의해 완료 순서와 무관하게 결과 자동 누적
- 순차 처리 대비 N배 병렬 처리로 응답 속도 최적화

### 5. SSE 실시간 스트리밍 (chat.py)

- `astream_events(version="v2")`로 노드 완료 이벤트 감지
- SSE 이벤트 타입:
  - `progress` — `{node, label, completed, total}` (진행 상태)
  - `result` — 최종 데이터 페이로드
  - `error` — 에러 메시지
- `/start/stream`: Manager → Searcher → Filter 순 스트리밍, `interrupt()` 감지 시 중단
- `/select/stream`: Dispatch → 병렬 Extract/Analyst → Collector → Writer 스트리밍, 서브그래프 완료 카운트 (`1/N`) 표시

### 6. 데이터 저장

- **북마크** — `data/bookmarks.json` (restaurant_name 기준 중복 제거)
- **공유 링크** — `data/shares.json` (8자리 UUID 코드, 결과 스냅샷 저장)
- **세션 체크포인트** — `data/checkpoints.db` (SQLite, LangGraph Checkpoint)

### 7. 프론트엔드 UI (React + Vite)

- **ChatPage** — 검색 입력 → 실시간 진행 표시 → 후보 카드 그리드 → 카카오맵 → 최종 리포트
- **후보 카드** — 체크박스 선택, 북마크 버튼, 공유 버튼, 링크 버튼
- **카카오맵** — 추천 식당 좌표 기반 마커 렌더링, 주소 지오코딩 지원, SDK 동적 로드 (10초 타임아웃)
- **SharePage** — 공유 코드(`/share/{code}`)로 최종 리포트 + 후보 카드 공개 조회
- **스타일링** — styled-components, CSS 변수, 반응형 레이아웃, 애니메이션(fade-in, spin, slide-up)

### 8. JSON 파싱 강건성

로컬 LLM의 불규칙한 출력 대응을 위한 3단계 폴백:
1. 원시 JSON 파싱
2. 마크다운 코드블록(` ```json `) 제거 후 재파싱
3. 정규식으로 JSON 객체 추출
- Qwen 모델의 `<think>` 블록 자동 제거 처리

---

## 🛠️ 기술 스택

### Backend

| 항목 | 내용 |
|---|---|
| Language | Python 3.14 |
| Framework | FastAPI · Uvicorn |
| AI Orchestration | LangGraph 1.1+ · LangChain 1.2+ |
| LLM | Ollama 로컬 모델 (qwen3.5:9b · exaone3.5:7.8b · gemma4) |
| 맛집 검색 | 카카오 로컬 API (REST) · Tavily Search API |
| 웹 크롤링 | Tavily Extract API |
| 세션 저장 | SQLite (`langgraph-checkpoint-sqlite`) |
| 데이터 저장 | JSON 파일 (북마크, 공유) |
| Streaming | SSE (Server-Sent Events) |
| HTTP Client | httpx (async) |

### Frontend

| 항목 | 내용 |
|---|---|
| Framework | React 18.3 · Vite 5 |
| Routing | React Router v6 |
| Styling | styled-components 6 |
| Map | 카카오맵 JavaScript SDK v2 |
| API | Fetch API · EventSource (SSE) |

---

## 🚀 시작하기

### 사전 요구 사항

- Python 3.14+
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

프로젝트 루트에 `.env` 파일을 생성합니다:

```env
# 필수
TAVILY_API_KEY=tvly-...              # https://tavily.com
KAKAO_REST_API_KEY=...               # 카카오 로컬 API 키

# 프론트엔드 (카카오맵)
VITE_KAKAO_MAP_KEY=...               # 카카오 JavaScript API 키
VITE_API_URL=http://localhost:8000

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_NUM_PARALLEL=3

# 세션 DB 경로
CHECKPOINT_DB_PATH=./data/checkpoints.db

# 선택 (LangSmith 트레이싱)
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=lsv2_pt_...
```

> 카카오 API 키 발급: [Kakao Developers](https://developers.kakao.com)  
> Tavily API 키 발급: [Tavily](https://tavily.com)

### 4. 프론트엔드 설정

```bash
cd frontend
npm install
```

### 5. 실행

터미널 두 개를 열어 각각 실행합니다.

**터미널 1 — 백엔드**
```bash
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
| `GET` | `/api/chat/start/stream` | 검색 시작 및 SSE 스트리밍 (`?query=`) |
| `GET` | `/api/chat/select/stream` | 식당 선택 후 분석 SSE (`?thread_id=&selected_indices=&action=`) |
| `POST` | `/api/chat/reject` | 결과 거절 및 재검색 (`{thread_id, feedback}`) |
| `POST` | `/api/chat/bookmark` | 북마크 추가 |
| `GET` | `/api/chat/bookmarks` | 북마크 목록 조회 |
| `POST` | `/api/chat/share` | 공유 링크 생성 (`{thread_id, final_answer, candidates}`) |
| `GET` | `/api/chat/share/{code}` | 공유 결과 조회 |
| `GET` | `/health` | 서버 상태 확인 |
| `GET` | `/docs` | Swagger API 문서 |

---

## 🔄 실행 흐름 예시

```
사용자: "홍대 근처 분위기 좋은 파스타 맛집 알려줘"

1. Manager   → location="홍대", category="파스타", max_price=null 추출
2. Searcher  → 카카오 로컬 API로 홍대 파스타 식당 검색 (좌표 포함)
             → Tavily로 웹 리뷰 수집 → LLM 배치로 식당명·요약 정제
3. Filter    → 리스트성 블로그 포스트 제거, 짧은 내용 필터링 → 6개 후보
4. [중단]    → 사용자에게 6개 후보 카드 + 카카오맵 마커 표시
5. 사용자    → "파스타 하우스", "라 루나" 2곳 선택 → approve
6. Dispatch  → 2곳을 독립 서브그래프에 병렬 투입
7. Extractor → 각 식당 URL 크롤링 → 메뉴·가격·영업시간·특징 추출
8. Analyst   → 선호도·예산 기반 장단점·추천 이유 분석
9. Collector → 2곳 결과 종합, 1순위 결정
10. Writer   → 최종 추천 리포트 마크다운 작성 및 표시
```

---

## 💡 기술적 인사이트

**LangGraph Command API + HITL**  
`interrupt()` + `Command(goto=..., update=...)` 조합으로 그래프 실행을 중단하고 사용자 입력을 받은 뒤 원하는 노드로 재개하는 패턴을 구현했습니다. Checkpoint를 SQLite에 저장하여 서버 재시작 후에도 세션이 유지됩니다.

**병렬 서브그래프 (`Send()` API)**  
사용자가 N개의 식당을 선택하면 `Send()` API로 각 식당을 독립 서브그래프에 동시 투입합니다. `Annotated[List, operator.add]` 타입으로 병렬 결과를 자동 누적해 순서와 관계없이 올바르게 집계됩니다.

**이중 검색 전략**  
카카오 로컬 API는 정확한 식당명·좌표·공식 URL을 제공하고, Tavily Search는 웹상의 실제 리뷰·블로그 콘텐츠를 커버합니다. 두 소스를 결합해 정확도와 풍부함을 동시에 확보합니다.

**로컬 LLM 역할 분담**  
단일 모델 대신 역할에 따라 3개 로컬 모델을 분산 배치했습니다.
- `qwen3.5:9b` → 한국어 NER (파라미터 추출, 필터링 판단)
- `exaone3.5:7.8b` → 긴 문서 분석 (크롤링 텍스트 이해, 인사이트 추출)
- `gemma4` → 자연스러운 문장 생성 (종합 요약, 리포트 작성)

**SSE 실시간 스트리밍**  
`astream_events(version="v2")`로 노드 완료 이벤트를 감지하고 `text/event-stream` 형식으로 프론트엔드에 즉시 전달합니다. 사용자는 분석이 진행되는 동안 각 단계 완료 현황을 실시간으로 확인할 수 있습니다.
