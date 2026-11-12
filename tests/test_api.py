"""API tests (demo mode, pre-populated temp warehouse).

Env vars are set BEFORE importing the app module so it points at the
tiny fixture database instead of the real one. The fixture has 6 rows,
so the app never triggers a first-run ingest here.
"""
import os
import tempfile

import pandas as pd

_tmp = tempfile.mkdtemp()
_db_path = os.path.join(_tmp, "api.db")
os.environ["APP_MODE"] = "demo"
os.environ["DB_PATH"] = _db_path

from src.warehouse import SQLiteWarehouse  # noqa: E402
from tests.conftest import TINY_COLUMNS, TINY_ROWS  # noqa: E402

_wh = SQLiteWarehouse(_db_path)
_wh.create_tables()
_wh.load_dataframe(pd.DataFrame(TINY_ROWS, columns=TINY_COLUMNS),
                   "RETAIL_TRANSACTIONS")
_wh.close()

from fastapi.testclient import TestClient  # noqa: E402

from src.app import app  # noqa: E402

client = TestClient(app)


def test_index_serves_ui():
    r = client.get("/")
    assert r.status_code == 200
    assert "GenAI Analytics Copilot" in r.text


def test_health_demo_mode():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    assert body["retail_rows"] == 6
    assert body["countries"] == 3


def test_ask_total_revenue():
    r = client.post("/api/ask", json={"question": "What was our total revenue?"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert abs(body["rows"][0][0] - 87.5) < 1e-9
    assert body["sql"]


def test_ask_unanswerable():
    r = client.post("/api/ask",
                    json={"question": "What is the weather in Paris?"})
    assert r.status_code == 200
    assert r.json()["success"] is False


def test_monitoring_records_queries():
    client.post("/api/ask", json={"question": "How many orders did we have?"})
    r = client.get("/api/monitoring")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["success_rate"] is not None
