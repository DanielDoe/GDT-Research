"""GDT-Research FastAPI backend."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "agents"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gdt_agents.api import router
from gdt_agents.db import init_db
from gdt_agents.jobs import shutdown_worker, start_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_worker()
    yield
    shutdown_worker()


app = FastAPI(
    title="Galveston Digital Twin API",
    version="0.1.0",
    description="Geospatial services and research agents for GDT-Research",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gdt-api"}


@app.get("/api/v1/study-area")
def study_area() -> dict:
    import json

    cfg = ROOT / "config" / "study_area.json"
    return json.loads(cfg.read_text(encoding="utf-8"))
