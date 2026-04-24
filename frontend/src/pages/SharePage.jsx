import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import styled from "styled-components";
import { api } from "../api";
import RestaurantCard from "../components/RestaurantCard";

const Page = styled.div`
  max-width: 820px;
  margin: 0 auto;
  padding: 48px 32px 80px;
`;

const Header = styled.div`
  margin-bottom: 32px;
  h1 { font-family: var(--font-serif); font-size: 1.8rem; color: var(--accent); }
  p  { color: var(--text-muted); font-size: 0.9rem; margin-top: 6px; }
`;

const Report = styled.div`
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px 28px;
  white-space: pre-wrap;
  line-height: 1.85;
  font-size: 0.92rem;
  margin-bottom: 24px;
`;

const Section = styled.section`
  margin-bottom: 32px;
  h2 {
    font-family: var(--font-serif);
    font-size: 1.15rem;
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }
`;

const BackLink = styled(Link)`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 0.88rem;
  margin-bottom: 28px;
  transition: color .2s;
  &:hover { color: var(--accent); }
`;

const QueryBadge = styled.div`
  display: inline-block;
  background: var(--accent-light);
  color: var(--accent);
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  margin-top: 8px;
`;

const Loading = styled.div`
  text-align: center;
  padding: 80px 0;
  color: var(--text-muted);
`;

const NotFound = styled.div`
  text-align: center;
  padding: 80px 0;
  color: var(--text-muted);
  h2 { margin-bottom: 12px; font-size: 1.2rem; }
`;

const CardGrid = styled.div`display: flex; flex-direction: column; gap: 12px;`;

export default function SharePage() {
  const { code } = useParams();
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  useEffect(() => {
    api.getShare(code)
      .then(setData)
      .catch(() => setError("공유 링크를 찾을 수 없습니다."))
      .finally(() => setLoading(false));
  }, [code]);

  if (loading) return <Page><Loading>불러오는 중...</Loading></Page>;

  if (error || !data) {
    return (
      <Page>
        <NotFound>
          <h2>😢 {error || "공유 링크를 찾을 수 없습니다."}</h2>
          <BackLink to="/">← 홈으로 돌아가기</BackLink>
        </NotFound>
      </Page>
    );
  }

  const { query, candidates = [], final_answer } = data.snapshot;

  return (
    <Page>
      <BackLink to="/">← 새 검색하기</BackLink>

      <Header>
        <h1>🍽️ AI 맛집 추천 결과</h1>
        {query && <QueryBadge>"{query}"</QueryBadge>}
        <p style={{ marginTop: 10 }}>공유된 AI 맛집 큐레이터 분석 리포트입니다.</p>
      </Header>

      {final_answer && (
        <Section>
          <h2>✨ AI 추천 리포트</h2>
          <Report>{final_answer}</Report>
        </Section>
      )}

      {candidates.length > 0 && (
        <Section>
          <h2>후보 식당</h2>
          <CardGrid>
            {candidates.map((r, i) => (
              <RestaurantCard
                key={i}
                restaurant={r}
                index={i}
                selectable={false}
                selected={false}
                onSelect={() => {}}
                onBookmark={() => {}}
                isBookmarked={false}
              />
            ))}
          </CardGrid>
        </Section>
      )}
    </Page>
  );
}
