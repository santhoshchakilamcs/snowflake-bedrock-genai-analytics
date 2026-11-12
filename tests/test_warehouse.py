"""Tests for the warehouse layer and monitoring log (SQLite, demo mode)."""
from src.monitoring import get_stats, log_query
from src.warehouse import TABLE_NAME


def test_load_and_count(tiny_warehouse, tiny_df):
    assert tiny_warehouse.row_count(TABLE_NAME) == len(tiny_df) == 6


def test_execute_query(tiny_warehouse):
    cols, rows = tiny_warehouse.execute(
        "SELECT SUM(QUANTITY * PRICE) AS revenue FROM RETAIL_TRANSACTIONS "
        "WHERE QUANTITY > 0")
    assert cols == ["revenue"]
    assert abs(rows[0][0] - 87.5) < 1e-9


def test_monitoring_log_and_stats(tiny_warehouse):
    log_query(tiny_warehouse, "demo", "What was our total revenue?",
              "SELECT 1", True, 12.5)
    log_query(tiny_warehouse, "demo", "nonsense question", None, False, 3.0,
              "cannot answer")
    stats = get_stats(tiny_warehouse)
    assert stats["total"] == 2
    assert stats["success_rate"] == 0.5
    assert stats["p50_ms"] == 12.5
    assert len(stats["recent"]) == 2
    assert stats["recent"][0]["QUESTION"] == "nonsense question"


def test_monitoring_empty(tiny_warehouse):
    stats = get_stats(tiny_warehouse)
    assert stats["total"] == 0
    assert stats["success_rate"] is None
