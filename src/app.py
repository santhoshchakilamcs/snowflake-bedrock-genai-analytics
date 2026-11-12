"""FastAPI service + minimal web UI for the GenAI analytics copilot.

Endpoints:
- GET  /                web UI
- GET  /api/health      mode, warehouse, row counts
- POST /api/ask         {"question": "..."} -> SQL, results, answer, latency
- GET  /api/monitoring  query totals, success rate, latency, recent queries

Run:  ./run.sh            (uvicorn on http://127.0.0.1:8003)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.config import AppConfig  # noqa: E402
from src.copilot import Copilot  # noqa: E402
from src.ingest import ingest  # noqa: E402
from src.warehouse import TABLE_NAME  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="Snowflake + Bedrock GenAI Analytics Copilot")
_cfg = AppConfig.from_env()
_copilot: Copilot | None = None


def get_copilot() -> Copilot:
    global _copilot
    if _copilot is None:
        _copilot = Copilot(_cfg)
        _, rows = _copilot.warehouse.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME}")
        if not rows or rows[0][0] == 0:
            print("Retail table is empty; running first-time ingest ...")
            ingest(_cfg, _copilot.warehouse)
            # Reload the country list now that data exists.
            _copilot.countries = _copilot._load_countries()
            if _copilot.mode == "demo":
                from src.translator import DemoTranslator

                _copilot.generator = DemoTranslator(
                    _copilot.retriever, _copilot.countries)
    return _copilot


class AskRequest(BaseModel):
    question: str


@app.get("/")
def index():
    return FileResponse(os.path.join(_cfg.project_root, "static", "index.html"))


@app.get("/api/health")
def health():
    cp = get_copilot()
    _, rows = cp.warehouse.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    return {
        "mode": cp.mode,
        "warehouse": cp.warehouse.name,
        "retail_rows": int(rows[0][0]) if rows else 0,
        "countries": len(cp.countries),
    }


@app.post("/api/ask")
def ask(req: AskRequest):
    cp = get_copilot()
    return JSONResponse(cp.ask(req.question))


@app.get("/api/monitoring")
def monitoring():
    cp = get_copilot()
    return JSONResponse(cp.stats())
