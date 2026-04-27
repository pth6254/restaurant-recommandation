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
  const mapRef   = useRef(null);
  const readyRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);

  const markReady = () => { readyRef.current = true; setReady(true); };

  useEffect(() => {
    if (!KAKAO_KEY) return;

    // SDK가 이미 완전히 초기화된 경우 (Map 생성자 존재 여부로 판별)
    if (window.kakao?.maps?.Map) {
      markReady();
      return;
    }

    // 스크립트가 이미 삽입됐지만 아직 load() 중인 경우 — 중복 삽입 방지
    if (window.kakao?.maps) {
      window.kakao.maps.load(markReady);
      return;
    }

    // SDK 동적 로드
    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_KEY}&libraries=services&autoload=false`;
    script.onload  = () => window.kakao.maps.load(markReady);
    script.onerror = () => setError("카카오맵 SDK 로드 실패 — API 키 또는 도메인 설정을 확인하세요.");
    document.head.appendChild(script);

    // 10초 타임아웃: load() 콜백이 영원히 안 올 때 에러 표시 (도메인 미등록 등)
    const timer = setTimeout(() => {
      if (!readyRef.current) {
        setError("카카오맵 초기화 타임아웃 — 카카오 개발자 콘솔에서 localhost 도메인을 등록했는지 확인하세요.");
      }
    }, 10_000);

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!ready || !mapRef.current) return;

    const { kakao } = window;
    const geocoder  = new kakao.maps.services.Geocoder();

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
      // 카카오 로컬 API 좌표가 있으면 geocoding 없이 바로 마커 생성
      if (r.y && r.x) {
        addMarker(map, parseFloat(r.y), parseFloat(r.x), r.name, r.score);
        return;
      }

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
        <span style={{ fontSize: "0.8rem" }}>frontend/.env 에 VITE_KAKAO_MAP_KEY 추가</span>
      </Placeholder>
    );
  }

  if (error) {
    return (
      <Placeholder>
        <span style={{ fontSize: "2rem" }}>⚠️</span>
        <span>{error}</span>
        <span style={{ fontSize: "0.78rem" }}>
          카카오 개발자 콘솔 → 앱 → 플랫폼 → Web에 localhost 등록 필요
        </span>
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
