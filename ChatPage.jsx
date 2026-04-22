import { useState, useRef, useEffect } from "react";
import styled, { keyframes } from "styled-components";
import { api } from "../api";
import RestaurantCard from "../components/RestaurantCard";
import KakaoMap from "../components/KakaoMap";

/* ── 애니메이션 ─────────────────────────────────────────── */
const spin = keyframes`to { transform: rotate(360deg); }`;
const fadeIn = keyframes`from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); }`;

/* ── 스타일 ───────────────────────────────────────────────── */
const Page = styled.div`
  max-width: 820px;
  margin: 0 auto;
  padding: 40px 32px;
`;

const Header = styled.div`
  margin-bottom: 40px;
  h1 { font-family: var(--font-serif); font-size: 2rem; color: var(--accent); }
  p  { color: var(--text-muted); font-size: 0.9rem; margin-top: 6px; }
`;

const SearchBox = styled.div`
  display: flex;
  gap: 12px;
  margin-bottom: 32px;
  input {
    flex: 1;
    padding: 14px 18px;
    font-size: 1rem;
    border-radius: var(--radius);
  }
`;

const SearchBtn = styled.button`
  padding: 14px 28px;
  background: var(--accent);
  color: #000;
  font-weight: 700;
  font-size: 0.95rem;
  border-radius: var(--radius);
  transition: opacity .2s;
  white-space: nowrap;
  &:hover    { opacity: 0.85; }
  &:disabled { opacity: 0.4; cursor: not-allowed; }
`;

const Section = styled.section`
  margin-bottom: 32px;
  h2 {
    font-family: var(--font-serif);
    font-size: 1.2rem;
    color: var(--text);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    span { color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-sans); margin-left: 8px; }
  }
`;

const CardGrid = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ConfirmBar = styled.div`
  position: sticky;
  bottom: 20px;
  background: var(--accent);
  color: #000;
  padding: 14px 20px;
  border-radius: var(--radius);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
  box-shadow: 0 8px 32px rgba(232,160,69,.35);
  cursor: pointer;
  transition: opacity .2s;
  &:hover { opacity: 0.9; }
`;

const Report = styled.div`
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px 28px;
  white-space: pre-wrap;
  line-height: 1.8;
  font-size: 0.92rem;
`;

const ShareBtn = styled.button`
  padding: 10px 20px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 0.85rem;
  background: var(--bg3);
  transition: all .2s;
  margin-top: 12px;
  &:hover { border-color: var(--accent); color: var(--accent); }
`;

/* ── SSE 진행 상황 표시 ──────────────────────────────────── */
const ProgressBox = styled.div`
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
  margin-bottom: 24px;
`;

const ProgressTitle = styled.div`
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;

  .spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: ${spin} .7s linear infinite;
  }
`;

const ProgressItem = styled.div`
  font-size: 0.88rem;
  color: var(--text);
  padding: 4px 0;
  animation: ${fadeIn} .3s ease;
`;

const Status = styled.div`
  color: var(--text-muted);
  font-size: 0.9rem;
  padding: 20px;
  text-align: center;
`;

/* ── 상수 ────────────────────────────────────────────────── */
const STEPS = {
  IDLE:      "idle",
  LOADING:   "loading",    // /start/stream 진행 중
  SELECT:    "select",     // 후보 선택 대기
  ANALYZING: "analyzing",  // /select/stream 진행 중
  DONE:      "done",
};

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/* ── 컴포넌트 ─────────────────────────────────────────────── */
export default function ChatPage() {
  const [query,      setQuery]      = useState("");
  const [step,       setStep]       = useState(STEPS.IDLE);
  const [threadId,   setThreadId]   = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [selected,   setSelected]   = useState([]);
  const [report,     setReport]     = useState("");
  const [progLogs,   setProgLogs]   = useState([]);   // SSE progress 메시지 누적
  const [location,   setLocation]   = useState("");
  const [category,   setCategory]   = useState("");
  const [bookmarked, setBookmarked] = useState(new Set());
  const [shareUrl,   setShareUrl]   = useState("");
  const [error,      setError]      = useState("");

  // EventSource 참조 (언마운트 시 close)
  const esRef = useRef(null);

  useEffect(() => {
    return () => esRef.current?.close();
  }, []);

  // ── SSE 공통 헬퍼 ──────────────────────────────────────
  const openSSE = (url, onResult) => {
    esRef.current?.close();

    const es = new EventSource(`${BASE_URL}${url}`);
    esRef.current = es;

    // progress 이벤트 → 로그 누적
    es.addEventListener("progress", (e) => {
      const data = JSON.parse(e.data);
      setProgLogs(prev => [...prev, data.label]);
    });

    // result 이벤트 → 최종 데이터 처리
    es.addEventListener("result", (e) => {
      const data = JSON.parse(e.data);
      es.close();
      onResult(data);
    });

    // error 이벤트 → 오류 표시
    es.addEventListener("error", (e) => {
      es.close();
      try {
        const data = JSON.parse(e.data);
        setError(data.message);
      } catch {
        setError("연결 오류가 발생했습니다.");
      }
      setStep(STEPS.IDLE);
    });

    // 연결 자체 오류
    es.onerror = () => {
      es.close();
      setError("서버 연결이 끊어졌습니다.");
      setStep(STEPS.IDLE);
    };
  };

  // ── 검색 시작 ──────────────────────────────────────────
  const handleSearch = () => {
    if (!query.trim()) return;
    setError("");
    setStep(STEPS.LOADING);
    setSelected([]);
    setReport("");
    setProgLogs([]);

    const loc = query.match(/([가-힣]+역|[가-힣]+동|[가-힣]+구|[가-힣]+시)/)?.[0] || "";
    const cat = query.match(/(일식|한식|중식|양식|카페|삼겹살|치킨|피자|파스타|라멘|스시)/)?.[0] || "";
    setLocation(loc);
    setCategory(cat);

    // ✅ SSE 연결: /start/stream
    openSSE(
      `/api/chat/start/stream?query=${encodeURIComponent(query)}`,
      (data) => {
        if (data.status === "no_results") {
          setError("조건에 맞는 맛집을 찾지 못했습니다. 다른 검색어를 시도해보세요.");
          setStep(STEPS.IDLE);
          return;
        }
        setThreadId(data.thread_id);
        setCandidates(data.candidates);
        setStep(STEPS.SELECT);
      }
    );
  };

  // ── 식당 선택 토글 ────────────────────────────────────
  const toggleSelect = (i) => {
    setSelected(prev =>
      prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]
    );
  };

  // ── 분석 시작 ─────────────────────────────────────────
  const handleAnalyze = () => {
    if (selected.length === 0) return;
    setStep(STEPS.ANALYZING);
    setProgLogs([]);

    const indices = selected.join(",");

    // ✅ SSE 연결: /select/stream
    openSSE(
      `/api/chat/select/stream?thread_id=${threadId}&selected_indices=${indices}&action=approve`,
      (data) => {
        setReport(data.final_answer);
        setStep(STEPS.DONE);
      }
    );
  };

  // ── 거절 후 재검색 ────────────────────────────────────
  const handleReject = async () => {
    const feedback = prompt("재검색 추가 조건을 입력하세요 (없으면 취소):");
    if (feedback === null) return;  // 취소

    setStep(STEPS.LOADING);
    setProgLogs([]);

    try {
      const data = await api.reject({ thread_id: threadId, feedback: feedback || null });
      if (data.status === "no_results") {
        setError("재검색에도 맛집을 찾지 못했습니다.");
        setStep(STEPS.IDLE);
        return;
      }
      setCandidates(data.candidates);
      setSelected([]);
      setStep(STEPS.SELECT);
    } catch (e) {
      setError(e.message);
      setStep(STEPS.SELECT);
    }
  };

  // ── 북마크 ───────────────────────────────────────────
  const handleBookmark = async (restaurant) => {
    try {
      await api.addBookmark({ restaurant_name: restaurant.name, location, category, url: restaurant.url });
      setBookmarked(prev => new Set([...prev, restaurant.name]));
    } catch {}
  };

  // ── 공유 ─────────────────────────────────────────────
  const handleShare = async () => {
    try {
      const data = await api.createShare({
        thread_id: threadId,
        snapshot: { query, candidates, final_answer: report },
      });
      const url = `${window.location.origin}/share/${data.share_code}`;
      setShareUrl(url);
      navigator.clipboard.writeText(url);
    } catch {}
  };

  // ── 렌더링 ───────────────────────────────────────────
  const isStreaming = step === STEPS.LOADING || step === STEPS.ANALYZING;

  return (
    <Page>
      <Header>
        <h1>🍽️ AI 맛집 큐레이터</h1>
        <p>찾고 싶은 맛집을 자유롭게 입력하세요 — AI가 분석하고 추천해드립니다</p>
      </Header>

      <SearchBox>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !isStreaming && handleSearch()}
          placeholder="예: 강남역 근처 분위기 좋은 일식집"
          disabled={isStreaming}
        />
        <SearchBtn onClick={handleSearch} disabled={isStreaming || !query.trim()}>
          검색
        </SearchBtn>
      </SearchBox>

      {error && <Status style={{ color: "var(--danger)" }}>{error}</Status>}

      {/* ── SSE 진행 상황 표시 ── */}
      {isStreaming && progLogs.length > 0 && (
        <ProgressBox>
          <ProgressTitle>
            <span className="spinner" />
            {step === STEPS.LOADING ? "맛집을 탐색하고 있습니다..." : "선택한 식당을 분석하고 있습니다..."}
          </ProgressTitle>
          {progLogs.map((log, i) => (
            <ProgressItem key={i}>{log}</ProgressItem>
          ))}
        </ProgressBox>
      )}

      {/* 진행 중인데 아직 로그 없을 때 */}
      {isStreaming && progLogs.length === 0 && (
        <Status>
          <span style={{ display: "inline-block", width: 18, height: 18, border: "2px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: `${spin} .7s linear infinite`, marginRight: 8, verticalAlign: "middle" }} />
          연결 중...
        </Status>
      )}

      {/* ── 후보 리스트 ── */}
      {(step === STEPS.SELECT || step === STEPS.DONE) && candidates.length > 0 && (
        <>
          {location && (
            <Section>
              <h2>📍 지도</h2>
              <KakaoMap restaurants={candidates} location={location} />
            </Section>
          )}

          <Section>
            <h2>
              후보 식당
              {step === STEPS.SELECT && (
                <span>분석할 식당을 선택하세요 (복수 선택 가능)</span>
              )}
            </h2>
            <CardGrid>
              {candidates.map((r, i) => (
                <RestaurantCard
                  key={i}
                  restaurant={r}
                  index={i}
                  selectable={step === STEPS.SELECT}
                  selected={selected.includes(i)}
                  onSelect={toggleSelect}
                  onBookmark={handleBookmark}
                  isBookmarked={bookmarked.has(r.name)}
                  location={location}
                  category={category}
                />
              ))}
            </CardGrid>
          </Section>

          {/* 거절 버튼 */}
          {step === STEPS.SELECT && (
            <div style={{ textAlign: "right", marginBottom: 12 }}>
              <button
                onClick={handleReject}
                style={{ padding: "8px 16px", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-muted)", fontSize: "0.85rem", background: "var(--bg3)" }}
              >
                ❌ 이 결과 마음에 안 들어요 (재검색)
              </button>
            </div>
          )}

          {/* 분석 시작 바 */}
          {step === STEPS.SELECT && selected.length > 0 && (
            <ConfirmBar onClick={handleAnalyze}>
              <span>선택한 식당 {selected.length}곳 심층 분석</span>
              <span>→</span>
            </ConfirmBar>
          )}
        </>
      )}

      {/* ── 최종 리포트 ── */}
      {step === STEPS.DONE && report && (
        <Section>
          <h2>✨ AI 추천 리포트</h2>
          <Report>{report}</Report>
          <ShareBtn onClick={handleShare}>
            {shareUrl ? `✅ 복사됨: ${shareUrl}` : "🔗 이 결과 공유하기"}
          </ShareBtn>
        </Section>
      )}
    </Page>
  );
}