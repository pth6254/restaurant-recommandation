import { useState } from "react";
import styled from "styled-components";
import { api } from "../api";
import RestaurantCard from "../components/RestaurantCard";
import KakaoMap from "../components/KakaoMap";

/* ── 스타일 ───────────────────────────────────────────── */
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

  &:hover   { opacity: 0.85; }
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

const Status = styled.div`
  color: var(--text-muted);
  font-size: 0.9rem;
  padding: 20px;
  text-align: center;

  .spinner {
    display: inline-block;
    width: 18px; height: 18px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin .7s linear infinite;
    margin-right: 8px;
    vertical-align: middle;
  }

  @keyframes spin { to { transform: rotate(360deg); } }
`;

/* ── 컴포넌트 ─────────────────────────────────────────── */
const STEPS = { IDLE: "idle", LOADING: "loading", SELECT: "select", ANALYZING: "analyzing", DONE: "done" };

export default function ChatPage() {
  const [query,     setQuery]     = useState("");
  const [step,      setStep]      = useState(STEPS.IDLE);
  const [threadId,  setThreadId]  = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [selected,  setSelected]  = useState([]);
  const [report,    setReport]    = useState("");
  const [location,  setLocation]  = useState("");
  const [category,  setCategory]  = useState("");
  const [bookmarked, setBookmarked] = useState(new Set());
  const [shareUrl,  setShareUrl]  = useState("");
  const [error,     setError]     = useState("");

  const handleSearch = async () => {
    if (!query.trim()) return;
    setError(""); setStep(STEPS.LOADING); setSelected([]); setReport("");

    try {
      const data = await api.startChat(query);
      setThreadId(data.thread_id);

      if (data.status === "no_results") {
        setError("조건에 맞는 맛집을 찾지 못했습니다. 다른 검색어를 시도해보세요.");
        setStep(STEPS.IDLE); return;
      }
      setCandidates(data.candidates);

      // location/category 추출 (간이)
      const loc = query.match(/([가-힣]+역|[가-힣]+동|[가-힣]+구|[가-힣]+시)/)?.[0] || "";
      const cat = query.match(/(일식|한식|중식|양식|카페|삼겹살|치킨|피자|파스타|라멘|스시)/)?.[0] || "";
      setLocation(loc); setCategory(cat);
      setStep(STEPS.SELECT);
    } catch (e) {
      setError(e.message); setStep(STEPS.IDLE);
    }
  };

  const toggleSelect = (i) => {
    setSelected(prev =>
      prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]
    );
  };

  const handleAnalyze = async () => {
    if (selected.length === 0) return;
    setStep(STEPS.ANALYZING);
    try {
      const data = await api.selectItems(threadId, selected);
      setReport(data.final_answer);
      setStep(STEPS.DONE);
    } catch (e) {
      setError(e.message); setStep(STEPS.SELECT);
    }
  };

  const handleBookmark = async (restaurant) => {
    try {
      await api.addBookmark({
        restaurant_name: restaurant.name,
        location, category,
        url: restaurant.url,
      });
      setBookmarked(prev => new Set([...prev, restaurant.name]));
    } catch {}
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
    } catch {}
  };

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
          onKeyDown={e => e.key === "Enter" && handleSearch()}
          placeholder="예: 강남역 근처 분위기 좋은 일식집"
          disabled={step === STEPS.LOADING || step === STEPS.ANALYZING}
        />
        <SearchBtn
          onClick={handleSearch}
          disabled={step === STEPS.LOADING || step === STEPS.ANALYZING || !query.trim()}
        >
          검색
        </SearchBtn>
      </SearchBox>

      {error && <Status style={{color:"var(--danger)"}}>{error}</Status>}

      {step === STEPS.LOADING && (
        <Status><span className="spinner" />AI가 맛집을 탐색하고 있습니다...</Status>
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

          {step === STEPS.SELECT && selected.length > 0 && (
            <ConfirmBar onClick={handleAnalyze}>
              <span>선택한 식당 {selected.length}곳 심층 분석</span>
              <span>→</span>
            </ConfirmBar>
          )}
        </>
      )}

      {step === STEPS.ANALYZING && (
        <Status><span className="spinner" />선택한 식당을 분석하고 있습니다...</Status>
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
