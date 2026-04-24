import styled from "styled-components";

const Card = styled.div`
  background: var(--card-bg);
  border: 2px solid ${({ $selected }) => ($selected ? "var(--accent)" : "var(--border)")};
  border-radius: var(--radius);
  padding: 18px 20px;
  cursor: ${({ $selectable }) => ($selectable ? "pointer" : "default")};
  transition: border-color .2s, box-shadow .2s, transform .15s;
  box-shadow: ${({ $selected }) => $selected ? "0 0 0 3px var(--accent-light)" : "var(--shadow)"};

  &:hover {
    border-color: ${({ $selectable }) => $selectable ? "var(--accent)" : "var(--border)"};
    transform: ${({ $selectable }) => $selectable ? "translateY(-1px)" : "none"};
    box-shadow: ${({ $selectable }) => $selectable ? "var(--shadow-md)" : "var(--shadow)"};
  }
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
`;

const Name = styled.h3`
  font-family: var(--font-serif);
  font-size: 1.05rem;
  color: var(--text);
  flex: 1;
`;

const Actions = styled.div`
  display: flex;
  gap: 6px;
  flex-shrink: 0;
`;

const IconBtn = styled.a`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px; height: 30px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg2);
  font-size: 0.85rem;
  color: var(--text-muted);
  cursor: pointer;
  transition: all .2s;
  text-decoration: none;
  &:hover { border-color: var(--accent); color: var(--accent); }
`;

const BookmarkBtn = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px; height: 30px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg2);
  font-size: 1rem;
  color: ${({ $active }) => ($active ? "#E53E3E" : "var(--text-muted)")};
  transition: all .2s;
  &:hover { border-color: #E53E3E; color: #E53E3E; }
`;

const Meta = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
  align-items: center;
`;

const Score = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.85rem;
  font-weight: 700;
  color: #B45309;
  background: #FEF3C7;
  padding: 2px 8px;
  border-radius: 20px;
`;

const Tag = styled.span`
  font-size: 0.78rem;
  color: var(--text-muted);
  background: var(--bg3);
  padding: 2px 8px;
  border-radius: 20px;
`;

const Address = styled.p`
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-bottom: 6px;
`;

const Summary = styled.p`
  font-size: 0.88rem;
  color: var(--text);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const SelectBadge = styled.div`
  margin-top: 12px;
  text-align: right;
  font-size: 0.8rem;
  font-weight: 600;
  color: ${({ $selected }) => ($selected ? "var(--accent)" : "var(--text-muted)")};
`;

export default function RestaurantCard({
  restaurant, index, selectable, selected,
  onSelect, onBookmark, isBookmarked,
}) {
  const { name, score, review_count, address, category, price_range, source_url, summary } = restaurant;

  const handleClick = () => {
    if (selectable) onSelect(index);
  };

  return (
    <Card $selected={selected} $selectable={selectable} onClick={handleClick}>
      <Header>
        <Name>{name}</Name>
        <Actions>
          {source_url && (
            <IconBtn href={source_url} target="_blank" rel="noopener noreferrer"
              onClick={e => e.stopPropagation()} title="원문 보기">
              ↗
            </IconBtn>
          )}
          <BookmarkBtn $active={isBookmarked}
            onClick={e => { e.stopPropagation(); onBookmark(restaurant); }}
            title={isBookmarked ? "북마크 완료" : "북마크 추가"}>
            {isBookmarked ? "♥" : "♡"}
          </BookmarkBtn>
        </Actions>
      </Header>

      <Meta>
        {score > 0 && <Score>★ {score.toFixed(1)}</Score>}
        {category && <Tag>{category}</Tag>}
        {price_range && <Tag>{price_range}</Tag>}
        {review_count && <Tag>리뷰 {review_count}개</Tag>}
      </Meta>

      {address && <Address>📍 {address}</Address>}
      {summary && <Summary>{summary}</Summary>}

      {selectable && (
        <SelectBadge $selected={selected}>
          {selected ? "✓ 선택됨" : "클릭하여 선택"}
        </SelectBadge>
      )}
    </Card>
  );
}
