import { useState, useRef, useEffect } from "react";
import styled, { keyframes } from "styled-components";
import { api } from "../api";
import RestaurantCard from "../components/RestaurantCard";
import KakaoMap from "../components/KakaoMap";

/* ── 애니메이션 ──────────────────────────────────────────── */
const spin   = keyframes`to { transform: rotate(360deg); }`;
const fadeIn = keyframes`from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); }`;
const fadeUp = keyframes`from { opacity:0; transform:translateY(28px); } to { opacity:1; transform:translateY(0); }`;
const blink  = keyframes`0%,100% { opacity:1; } 50% { opacity:0; }`;

/* ── 히어로 (IDLE 전용) ──────────────────────────────────── */
const Hero = styled.div`
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px 80px;
  background: linear-gradient(160deg, #FAFAF8 0%, #F5EDE3 55%, #FAFAF8 100%);
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute; inset: 0;
    background:
      radial-gradient(ellipse 60% 50% at 20% 30%, rgba(212,98,42,0.08) 0%, transparent 100%),
      radial-gradient(ellipse 50% 40% at 80% 70%, rgba(212,98,42,0.05) 0%, transparent 100%);
    pointer-events: none;
  }
`;

const HeroContent = styled.div`
  position: relative;
  max-width: 660px;
  width: 100%;
  text-align: center;
  animation: ${fadeUp} 0.65s ease both;
`;

const HeroBadge = styled.div`
  display: inline-block;
  padding: 5px 16px;
  border-radius: 999px;
  background: var(--accent-light);
  border: 1px solid rgba(212,98,42,0.2);
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  margin-bottom: 22px;
`;

const HeroTitle = styled.h1`
  font-family: var(--font-serif);
  font-size: clamp(2.2rem, 6vw, 3.4rem);
  color: var(--text);
  line-height: 1.2;
  margin-bottom: 16px;
  letter-spacing: -0.5px;

  em { color: var(--accent); font-style: normal; }
`;

const HeroSub = styled.p`
  color: var(--text-muted);
  font-size: 1rem;
  line-height: 1.8;
  margin-bottom: 40px;
`;

/* ── 검색 패널 ───────────────────────────────────────────── */
const SearchPanel = styled.div`
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 12px 48px rgba(0,0,0,0.09), 0 2px 8px rgba(0,0,0,0.04);
`;

const SearchInputRow = styled.div`
  display: flex;
  gap: 10px;
  margin-bottom: 12px;

  @media (max-width: 520px) { flex-direction: column; }
`;

const InputWrapper = styled.div`
  flex: 1;
  position: relative;

  .icon {
    position: absolute;
    left: 13px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 1rem;
    pointer-events: none;
    line-height: 1;
  }

  input {
    width: 100%;
    padding: 13px 14px 13px 38px;
    font-size: 0.95rem;
    border-radius: 10px;
  }
`;

const SearchBtn = styled.button`
  width: 100%;
  padding: 14px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
  border-radius: 10px;
  transition: opacity .2s, transform .1s;
  letter-spacing: 0.01em;
  &:hover    { opacity: 0.88; transform: translateY(-1px); }
  &:active   { transform: translateY(0); }
  &:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
`;

/* ── 예시 칩 ─────────────────────────────────────────────── */
const ChipList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 22px;
`;

const Chip = styled.button`
  padding: 7px 15px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--text-muted);
  font-size: 0.82rem;
  transition: all .2s;
  &:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-light);
    transform: translateY(-1px);
  }
`;

/* ── How it works ────────────────────────────────────────── */
const StepsRow = styled.div`
  display: flex;
  justify-content: center;
  align-items: flex-start;
  gap: 0;
  margin-top: 56px;

  @media (max-width: 520px) { flex-direction: column; align-items: center; gap: 20px; }
`;

const StepItem = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 140px;
  text-align: center;
  position: relative;

  &:not(:last-child)::after {
    content: '→';
    position: absolute;
    right: -14px;
    top: 16px;
    color: var(--border);
    font-size: 1.1rem;

    @media (max-width: 520px) { display: none; }
  }

  .step-icon {
    width: 50px; height: 50px;
    border-radius: 50%;
    background: var(--accent-light);
    border: 1px solid rgba(212,98,42,0.15);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.35rem;
  }

  strong { font-size: 0.83rem; color: var(--text); }

  p {
    font-size: 0.75rem;
    color: var(--text-muted);
    line-height: 1.5;
    margin-top: -4px;
  }
`;

/* ── 컴팩트 헤더 (IDLE 이후) ─────────────────────────────── */
const CompactHeader = styled.div`
  background: var(--card-bg);
  border-bottom: 1px solid var(--border);
  padding: 10px 20px;
  position: sticky;
  top: 0;
  z-index: 20;
  box-shadow: 0 1px 8px rgba(0,0,0,0.06);
`;

const CompactInner = styled.div`
  max-width: 820px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const CompactLogo = styled.span`
  font-family: var(--font-serif);
  font-size: 1rem;
  color: var(--accent);
  white-space: nowrap;
  flex-shrink: 0;
  margin-right: 4px;
`;

const CompactInputWrapper = styled.div`
  flex: 1;
  position: relative;
  min-width: 0;

  .icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.85rem;
    pointer-events: none;
    line-height: 1;
  }

  input {
    width: 100%;
    padding: 8px 10px 8px 28px;
    font-size: 0.85rem;
    border-radius: 8px;
  }
`;

const CompactBtn = styled.button`
  padding: 8px 18px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: 0.85rem;
  border-radius: 8px;
  white-space: nowrap;
  transition: opacity .2s;
  &:hover    { opacity: 0.85; }
  &:disabled { opacity: 0.4; cursor: not-allowed; }
`;

/* ── 결과 영역 공통 ──────────────────────────────────────── */
const Page = styled.div`
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 24px 80px;
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

const Cursor = styled.span`
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--accent);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: ${blink} 0.8s step-end infinite;
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
  input { flex: 1; padding: 10px 14px; font-size: 0.9rem; border-radius: 8px; }
  button { padding: 10px 16px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; }
`;

const ConfirmFeedbackBtn = styled.button`background: var(--accent); color: #fff;`;
const CancelFeedbackBtn  = styled.button`border: 1px solid var(--border); color: var(--text-muted); background: var(--bg3);`;

const RejectBtn = styled.button`
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 0.85rem;
  background: var(--bg3);
`;

/* ── 예시 칩 데이터 ──────────────────────────────────────── */
const EXAMPLES = [
  { location: "강남역",  category: "파스타"  },
  { location: "홍대",    category: "카페"    },
  { location: "합정",    category: "삼겹살"  },
  { location: "서울역",  category: "한식"    },
  { location: "신촌",    category: "일식"    },
  { location: "이태원",  category: "양식"    },
  { location: "건대입구", category: "치킨"   },
];

const STEPS = {
  IDLE:      "idle",
  LOADING:   "loading",
  SELECT:    "select",
  ANALYZING: "analyzing",
  DONE:      "done",
};

export default function ChatPage() {
  const [locationInput, setLocationInput] = useState("");
  const [categoryInput, setCategoryInput] = useState("");
  const [step,          setStep]          = useState(STEPS.IDLE);
  const [threadId,      setThreadId]      = useState(null);
  const [candidates,    setCandidates]    = useState([]);
  const [selected,      setSelected]      = useState([]);
  const [report,        setReport]        = useState("");
  const [progLogs,      setProgLogs]      = useState([]);
  const [location,      setLocation]      = useState("");
  const [category,      setCategory]      = useState("");
  const [bookmarked,    setBookmarked]    = useState(new Set());
  const [shareUrl,      setShareUrl]      = useState("");
  const [error,         setError]         = useState("");
  const [showFeedback,  setShowFeedback]  = useState(false);
  const [feedbackText,  setFeedbackText]  = useState("");
  const [isTyping,      setIsTyping]      = useState(false);

  const esRef        = useRef(null);
  const typewriterRef = useRef(null);

  useEffect(() => () => {
    esRef.current?.close();
    clearInterval(typewriterRef.current);
  }, []);

  const combinedQuery = [locationInput, categoryInput].filter(Boolean).join(" ");
  const isStreaming   = step === STEPS.LOADING || step === STEPS.ANALYZING;

  /* ── SSE 공통 헬퍼 ──────────────── */
  const openSSE = (es, onResult) => {
    esRef.current?.close();
    esRef.current = es;
    let done = false;

    es.addEventListener("progress", (e) => {
      setProgLogs(prev => [...prev, JSON.parse(e.data).label]);
    });
    es.addEventListener("result", (e) => {
      done = true;
      es.close();
      onResult(JSON.parse(e.data));
    });
    es.addEventListener("error", (e) => {
      if (done) return;
      es.close();
      try { setError(JSON.parse(e.data).message); }
      catch { setError("연결 오류가 발생했습니다."); }
      setStep(STEPS.IDLE);
    });
    es.onerror = () => {
      if (done) return;
      es.close();
      setError("백엔드 서버에 연결할 수 없습니다. uvicorn이 실행 중인지 확인하세요.");
      setStep(STEPS.IDLE);
    };
  };

  /* ── 타이핑 효과 ────────────────── */
  const startTypewriter = (fullText) => {
    clearInterval(typewriterRef.current);
    setReport("");
    setIsTyping(true);
    let i = 0;
    typewriterRef.current = setInterval(() => {
      i++;
      setReport(fullText.slice(0, i));
      if (i >= fullText.length) {
        clearInterval(typewriterRef.current);
        setIsTyping(false);
      }
    }, 8);
  };

  /* ── 검색 시작 ──────────────────── */
  const handleSearch = () => {
    if (!combinedQuery || isStreaming) return;
    clearInterval(typewriterRef.current);
    setIsTyping(false);
    setError("");
    setStep(STEPS.LOADING);
    setSelected([]);
    setReport("");
    setProgLogs([]);
    setLocation("");
    setCategory("");
    setShareUrl("");
    setShowFeedback(false);

    openSSE(api.startStream(combinedQuery), (data) => {
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

  const applyChip = ({ location: loc, category: cat }) => {
    setLocationInput(loc);
    setCategoryInput(cat);
  };

  const toggleSelect = (i) => setSelected(prev =>
    prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]
  );

  const handleAnalyze = () => {
    if (selected.length === 0) return;
    setStep(STEPS.ANALYZING);
    setProgLogs([]);
    setReport("");
    openSSE(api.selectStream(threadId, selected.join(",")), (data) => {
      setStep(STEPS.DONE);
      startTypewriter(data.final_answer);
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
        location, category,
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
        snapshot: { query: combinedQuery, candidates, final_answer: report },
      });
      const url = `${window.location.origin}/share/${data.share_code}`;
      setShareUrl(url);
      navigator.clipboard.writeText(url);
    } catch {
      setError("공유 링크 생성에 실패했습니다.");
    }
  };

  /* ════════════════════════════════
     히어로 화면 (IDLE)
  ════════════════════════════════ */
  if (step === STEPS.IDLE) {
    return (
      <Hero>
        <HeroContent>
          <HeroBadge>LangGraph 멀티 에이전트</HeroBadge>

          <HeroTitle>
            원하는 맛집,<br />
            <em>AI가 찾아드립니다</em>
          </HeroTitle>
          <HeroSub>
            지역과 음식 종류를 입력하면 AI가 실시간으로 맛집을 탐색하고<br />
            심층 분석한 추천 리포트를 제공합니다
          </HeroSub>

          <SearchPanel>
            <SearchInputRow>
              <InputWrapper>
                <span className="icon">📍</span>
                <input
                  value={locationInput}
                  onChange={e => setLocationInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="지역 (예: 강남역, 홍대)"
                  autoFocus
                />
              </InputWrapper>
              <InputWrapper>
                <span className="icon">🍽️</span>
                <input
                  value={categoryInput}
                  onChange={e => setCategoryInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder="음식 (예: 파스타, 삼겹살)"
                />
              </InputWrapper>
            </SearchInputRow>
            <SearchBtn onClick={handleSearch} disabled={!combinedQuery}>
              AI 맛집 탐색 시작
            </SearchBtn>
          </SearchPanel>

          {error && (
            <Status style={{ color: "var(--danger)", marginTop: 12 }}>{error}</Status>
          )}

          <ChipList>
            {EXAMPLES.map((ex) => (
              <Chip key={`${ex.location}-${ex.category}`} onClick={() => applyChip(ex)}>
                📍 {ex.location} &nbsp;·&nbsp; {ex.category}
              </Chip>
            ))}
          </ChipList>

          <StepsRow>
            <StepItem>
              <div className="step-icon">🗺️</div>
              <strong>지역 · 음식 입력</strong>
              <p>찾고 싶은 지역과 음식을 입력하세요</p>
            </StepItem>
            <StepItem>
              <div className="step-icon">🤖</div>
              <strong>AI 실시간 탐색</strong>
              <p>멀티 에이전트가 협력해 맛집 수집·분석</p>
            </StepItem>
            <StepItem>
              <div className="step-icon">✨</div>
              <strong>리포트 수령</strong>
              <p>원하는 식당 선택 후 심층 추천 리포트 확인</p>
            </StepItem>
          </StepsRow>
        </HeroContent>
      </Hero>
    );
  }

  /* ════════════════════════════════
     결과 화면 (IDLE 이후)
  ════════════════════════════════ */
  return (
    <>
      <CompactHeader>
        <CompactInner>
          <CompactLogo>🍽️ AI 맛집</CompactLogo>
          <CompactInputWrapper>
            <span className="icon">📍</span>
            <input
              value={locationInput}
              onChange={e => setLocationInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSearch()}
              placeholder="지역"
              disabled={isStreaming}
            />
          </CompactInputWrapper>
          <CompactInputWrapper>
            <span className="icon">🍽️</span>
            <input
              value={categoryInput}
              onChange={e => setCategoryInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSearch()}
              placeholder="음식"
              disabled={isStreaming}
            />
          </CompactInputWrapper>
          <CompactBtn onClick={handleSearch} disabled={isStreaming || !combinedQuery}>
            재검색
          </CompactBtn>
        </CompactInner>
      </CompactHeader>

      <Page>
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
          <Status><Spinner />연결 중...</Status>
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
                    <RejectBtn onClick={() => setShowFeedback(true)}>
                      ❌ 이 결과 마음에 안 들어요 (재검색)
                    </RejectBtn>
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
            <Report>
              {report}
              {isTyping && <Cursor />}
            </Report>
            {!isTyping && (
              <ShareBtn onClick={handleShare}>
                {shareUrl ? `✅ 복사됨: ${shareUrl}` : "🔗 이 결과 공유하기"}
              </ShareBtn>
            )}
          </Section>
        )}
      </Page>
    </>
  );
}
