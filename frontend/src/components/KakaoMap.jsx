import { useState, useEffect, useRef } from "react";
import styled from "styled-components";

const MapWrap = styled.div`
  width: 100%;
  height: 320px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  overflow: hidden;
`;

const Placeholder = styled.div`
  width: 100%;
  height: 320px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--bg3);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 0.9rem;
`;

const KAKAO_KEY = import.meta.env.VITE_KAKAO_MAP_KEY;

export default function KakaoMap({ restaurants, location }) {
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!KAKAO_KEY) return;

    // 이미 로드된 경우
    if (window.kakao?.maps) {
      setReady(true);
      return;
    }

    // SDK 동적 로드
    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_KEY}&libraries=services&autoload=false`;
    script.onload = () => window.kakao.maps.load(() => setReady(true));
    script.onerror = () => console.error("카카오맵 SDK 로드 실패");
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (!ready || !mapRef.current) return;

    const { kakao } = window;
    const geocoder = new kakao.maps.services.Geocoder();

    const map = new kakao.maps.Map(mapRef.current, {
      center: new kakao.maps.LatLng(37.5665, 126.978),
      level: 5,
    });

    if (location) {
      geocoder.addressSearch(location, (result, status) => {
        if (status === kakao.maps.services.Status.OK) {
          map.setCenter(new kakao.maps.LatLng(result[0].y, result[0].x));
        }
      });
    }

    restaurants.forEach((r) => {
      const query = r.address || `${location} ${r.name}`;
      geocoder.addressSearch(query, (result, status) => {
        if (status !== kakao.maps.services.Status.OK) {
          const ps = new kakao.maps.services.Places();
          ps.keywordSearch(`${location} ${r.name}`, (places, s) => {
            if (s !== kakao.maps.services.Status.OK) return;
            addMarker(map, places[0].y, places[0].x, r.name, r.score);
          });
          return;
        }
        addMarker(map, result[0].y, result[0].x, r.name, r.score);
      });
    });
  }, [ready, restaurants, location]);

  if (!KAKAO_KEY) {
    return (
      <Placeholder>
        <span style={{ fontSize: "2rem" }}>🗺️</span>
        <span>카카오맵 API 키를 설정하면 지도가 표시됩니다.</span>
        <span style={{ fontSize: "0.8rem" }}>.env 파일에 VITE_KAKAO_MAP_KEY 추가</span>
      </Placeholder>
    );
  }

  if (!ready) {
    return (
      <Placeholder>
        <span style={{ fontSize: "2rem" }}>🗺️</span>
        <span>지도 로딩 중...</span>
      </Placeholder>
    );
  }

  return <MapWrap ref={mapRef} />;
}

function addMarker(map, lat, lng, name, score) {
  const { kakao } = window;
  const pos = new kakao.maps.LatLng(lat, lng);

  const marker = new kakao.maps.Marker({ map, position: pos, title: name });

  const infowindow = new kakao.maps.InfoWindow({
    content: `
      <div style="padding:8px 12px;font-size:13px;font-weight:600;white-space:nowrap;">
        ${name}${score > 0 ? ` <span style="color:#B45309">★${score.toFixed(1)}</span>` : ""}
      </div>`,
  });

  kakao.maps.event.addListener(marker, "click", () => {
    infowindow.open(map, marker);
  });
}
