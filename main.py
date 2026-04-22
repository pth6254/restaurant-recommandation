"""
main.py
-------
FastAPI 서버 진입점.

실행: uvicorn main:app --reload --port 8000
"""

import os
import requests
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chat import router as chat_router


# ────────────────────────────────────────────
# 시작 시 Ollama 연결 확인
# ────────────────────────────────────────────
def check_ollama():
    base_url       = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    required_models = ["qwen3.5:9b", "exaone3.5:7.8b", "gemma4:latest"]

    print(f"\n🔌 Ollama 연결 확인 ({base_url})")
    try:
        resp      = requests.get(f"{base_url}/api/tags", timeout=5)
        available = [m["name"] for m in resp.json().get("models", [])]
        for model in required_models:
            found  = any(model.split(":")[0] in a for a in available)
            status = "✅" if found else "❌ 없음 → ollama pull " + model
            print(f"  {status}  {model}")
    except Exception as e:
        print(f"  ⚠️ Ollama 확인 실패: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_ollama()
    yield


# ────────────────────────────────────────────
# FastAPI 앱
# ────────────────────────────────────────────
app = FastAPI(
    title="AI 맛집 큐레이터",
    description="LangGraph 기반 멀티 에이전트 맛집 추천 시스템",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok"}