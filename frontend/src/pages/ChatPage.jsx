import { useState, useRef, useEffect } from "react";
import styled, { keyframes } from "styled-components";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import RestaurantCard from "../components/RestaurantCard";
import KakaoMap from "../components/KakaoMap";

const spin   = keyframes`to { transform: rotate(360deg); }`;
const fadeIn = keyframes`from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); }`;

const Page = styled.div`
  max-width: 820px;
  margin: 0 auto;
  padding: 48px 32px 80px;
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
  color: #fff;
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
    font-size: 1.15rem;
    color: var(--text);
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    span { color: var(--text-muted); font-size: 0.78rem; font-family: var(--font-sans); margin-left: 8px; }
  }
`;

const CardGrid = styled.div`display: flex; flex-direction: column; gap: 12px;`;

const ConfirmBar = styled.div`
  position: sticky;
  bottom: 20px;
  background: var(--accent);
  color: #fff;
  padding: 14px 20px;
  border-radius: var(--radius);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
  box-shadow: 0 8px 32px rgba(212,98,42,.35);
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
  line-height: 1.85;
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
  margin-bottom: 10px;
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
  padding: 3px 0;
  animation: ${fadeIn} .3s ease;
`;

const Spinner = styled.span`
  display: inline-block;
  width: 18px; height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: ${spin} .7s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
`;

const Status = styled.div`
  color: var(--text-muted);
  font-size: 0.9rem;
  padding: 20px;
  text-align: center;
`;

const FeedbackBox = styled.div`
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
  input {
    flex: 1;
    padding: 10px 14px;
    font-size: 0.9rem;
    border-radius: 8px;
  }
  button {
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
  }
`;

const ConfirmFeedbackBtn = styled.button`
  background: var(--accent);
  color: #fff;
`;

const CancelFeedbackBtn = styled.button`
  border: 1px solid var(--border);
  color: var(--text-muted);
  background: var(--bg3);
`;

const STEPS = {
  IDLE:      "idle",
  LOADING:   "loading",
  SELECT:    "select",
  ANALYZING: "analyzing",
  DONE:      "done",
};

export default function ChatPage() {
  const navigate = useNavigate();

  const [query,           setQuery]           = useState("");
  const [step,            setStep]            = useState(STEPS.IDLE);
  const [threadId,        setThreadId]        = useState(null);
  const [candidates,      setCandidates]      = useState([]);
  const [selected,        setSelected]        = useState([]);
  const [report,          setReport]          = useState("");
  const [progLogs,        setProgLogs]        = useState([]);
  const [location,        setLocation]        = useState("");
  const [category,        setCategory]        = useState("");
  const [bookmarked,      setBookmarked]      = useState(new Set());
  const [shareUrl,        setShareUrl]        = useState("");
  const [error,           setError]           = useState("");
  const [showFeedback,    setShowFeedback]    = useState(false);
  const [feedbackText,    setFeedbackText]    = useState("");

  const esRef = useRef(null);

  useEffect(() => () => esRef.current?.close(), []);

  const openSSE = (es, onResult) => {
    esRef.current?.close();
    esRef.current = es;

    let done = false;  // result 수신 후 onerror 무시 플래그

    es.addEventListener("progress", (e) => {
      const data = JSON.parse(e.data);
      setProgLogs(prev => [...prev, data.label]);
    });

    es.addEventListener("result", (e) => {
      done = true;
      const data = JSON.parse(e.data);
      es.close();
      onResult(data);
    });

    es.addEventListener("error", (e) => {
      if (done) return;
      es.close();
      try {
        const data = JSON.parse(e.data);
        setError(data.message);
      } catch {
        setError("연결 오류가 발생했습니다.");
      }
      setStep(STEPS.IDLE);
    });

    es.onerror = () => {
      if (done) return;  // result 이미 수신했으면 무시
      es.close();
      setError("백엔드 서버에 연결할 수 없습니다. uvicorn이 실행 중인지 확인하세요.");
      setStep(STEPS.IDLE);
    };
  };

  const handleSearch = () => {
    if (!query.trim()) return;
    setError("");
    setStep(STEPS.LOADING);
    setSelected([]);
    setReport("");
    setProgLogs([]);
    setLocation("");
    setCategory("");
    setShareUrl("");
    setShowFeedback(false);

    openSSE(api.startStream(query), (data) => {
      if (data.status === "no_results") {
        setError("조건에 맞는 맛집을 찾지 못했습니다. 다른 검색어를 시도해보세요.");
        setStep(STEPS.IDLE);
        return;
      }
      setThreadId(data.thread_id);
      setCandidates(data.candidates);
      setLocation(data.location || "");
      setCategory(data.category || "");
      setStep(STEPS.SELECT);
    });
  };

  const toggleSelect = (i) => {
    setSelected(prev => prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]);
  };

  const handleAnalyze = () => {
    if (selected.length === 0) return;
    setStep(STEPS.ANALYZING);
    setProgLogs([]);

    openSSE(api.selectStream(threadId, selected.join(",")), (data) => {
      setReport(data.final_answer);
      setStep(STEPS.DONE);
    });
  };

  const handleRejectConfirm = async () => {
    setShowFeedback(false);
    const feedback = feedbackText.trim() || null;
    setFeedbackText("");
    setStep(STEPS.LOADING);
    setProgLogs([]);

    try {
      const data = await api.reject({ thread_id: threadId, feedback });
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

  const handleBookmark = async (restaurant) => {
    try {
      await api.addBookmark({
        restaurant_name: restaurant.name,
        location,
        category,
        url: restaurant.source_url,
        score: restaurant.score,
        summary: restaurant.summary,
      });
      setBookmarked(prev => new Set([...prev, restaurant.name]));
    } catch {
      setError("북마크 저장에 실패했습니다.");
    }
  };

  const handleShare = async () => {
    try {
      const data = await api.createShare({
        thread_id: threadId,
        snapshot: { query, candidates, final_answer: report },
      });
      const url = `${window.location.origin}/share/${data.share_code}`;
      setShareUrl(url);
      navigator.clipboard.writeText(url);
    } catch {
      setError("공유 링크 생성에 실패했습니다.");
    }
  };

  const isStreaming = step === STEPS.LOADING || step === STEPS.ANALYZING;

  return (
    <Page>
      <Header>
        <h1>🍽️ AI 맛집 큐레이터</h1>
        <p>찾고 싶은 맛집을 자유롭게 입력하세요 — AI가 분석하고 추천해드립니다</p>
      </Header>

      <SearchBox>
        <input
          id="search-query"
          name="search-query"
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

      {isStreaming && progLogs.length > 0 && (
        <ProgressBox>
          <ProgressTitle>
            <span className="spinner" />
            {step === STEPS.LOADING ? "맛집을 탐색하고 있습니다..." : "선택한 식당을 분석하고 있습니다..."}
          </ProgressTitle>
          {progLogs.map((log, i) => <ProgressItem key={i}>{log}</ProgressItem>)}
        </ProgressBox>
      )}

      {isStreaming && progLogs.length === 0 && (
        <Status>
          <Spinner />
          연결 중...
        </Status>
      )}

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
              {step === STEPS.SELECT && <span>분석할 식당을 선택하세요 (복수 선택 가능)</span>}
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

          {step === STEPS.SELECT && (
            <>
              {showFeedback ? (
                <FeedbackBox>
                  <input
                    id="feedback-text"
                    name="feedback-text"
                    value={feedbackText}
                    onChange={e => setFeedbackText(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleRejectConfirm()}
                    placeholder="추가 조건을 입력하세요 (예: 주차 가능, 단체석 있는)"
                    autoFocus
                  />
                  <ConfirmFeedbackBtn onClick={handleRejectConfirm}>재검색</ConfirmFeedbackBtn>
                  <CancelFeedbackBtn onClick={() => setShowFeedback(false)}>취소</CancelFeedbackBtn>
                </FeedbackBox>
              ) : (
                <div style={{ textAlign: "right", marginBottom: 12 }}>
                  <button
                    onClick={() => setShowFeedback(true)}
                    style={{
                      padding: "8px 16px", border: "1px solid var(--border)",
                      borderRadius: 8, color: "var(--text-muted)",
                      fontSize: "0.85rem", background: "var(--bg3)",
                    }}
                  >
                    ❌ 이 결과 마음에 안 들어요 (재검색)
                  </button>
                </div>
              )}

              {selected.length > 0 && (
                <ConfirmBar onClick={handleAnalyze}>
                  <span>선택한 식당 {selected.length}곳 심층 분석</span>
                  <span>→</span>
                </ConfirmBar>
              )}
            </>
          )}
        </>
      )}

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
