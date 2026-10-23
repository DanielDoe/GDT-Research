"""GDT-Research FastAPI backend (Phase 1 stub)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Galveston Digital Twin API",
    version="0.1.0",
    description="Geospatial object and scene services for GDT-Research",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gdt-api"}


@app.get("/api/v1/study-area")
def study_area() -> dict:
    from pathlib import Path
    import json

    cfg = Path(__file__).resolve().parents[2] / "config" / "study_area.json"
    return json.loads(cfg.read_text(encoding="utf-8"))
