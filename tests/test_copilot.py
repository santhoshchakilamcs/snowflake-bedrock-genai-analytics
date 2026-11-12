"""End-to-end copilot tests on the tiny fixture warehouse (demo mode)."""
from src.config import AppConfig
from src.copilot import Copilot


def _copilot(tiny_warehouse):
    cfg = AppConfig.from_env()
    cfg.mode = "demo"
    return Copilot(cfg, warehouse=tiny_warehouse)


def test_ask_total_revenue(tiny_warehouse):
    cp = _copilot(tiny_warehouse)
    try:
        res = cp.ask("What was our total revenue?")
        assert res["success"] is True
        assert res["mode"] == "demo"
        assert res["sql"]
        assert abs(res["rows"][0][0] - 87.5) < 1e-9
        assert "87.50" in res["answer"]
    finally:
        cp.close()


def test_ask_revenue_by_year(tiny_warehouse):
    cp = _copilot(tiny_warehouse)
    try:
        res = cp.ask("What was total revenue in 2010?")
        assert res["success"] is True
        assert abs(res["rows"][0][0] - 50.0) < 1e-9
    finally:
        cp.close()


def test_ask_top_product(tiny_warehouse):
    cp = _copilot(tiny_warehouse)
    try:
        res = cp.ask("What is the best-selling product by quantity?")
        assert res["success"] is True
        assert res["rows"][0][0] == "RED WIDGET"
    finally:
        cp.close()


def test_ask_unanswerable_logs_failure(tiny_warehouse):
    cp = _copilot(tiny_warehouse)
    try:
        res = cp.ask("What is the weather like in Paris tomorrow?")
        assert res["success"] is False
        assert res["error"]
        stats = cp.stats()
        assert stats["total"] >= 1
        assert stats["success_rate"] < 1.0
    finally:
        cp.close()


def test_ask_empty_question(tiny_warehouse):
    cp = _copilot(tiny_warehouse)
    try:
        res = cp.ask("   ")
        assert res["success"] is False
    finally:
        cp.close()
