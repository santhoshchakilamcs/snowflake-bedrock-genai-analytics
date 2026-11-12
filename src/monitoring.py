"""Query monitoring: every copilot query is logged, and the log backs the
monitoring view (totals, success rate, latency p50/p95, recent queries).
The log lives in the warehouse itself (QUERY_LOG table), so it works the
same in demo (SQLite) and live (Snowflake) mode.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from .warehouse import LOG_TABLE_NAME, Warehouse


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def log_query(wh: Warehouse, mode: str, question: str, sql: str | None,
              success: bool, latency_ms: float, error: str | None = None) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    safe_q = question.replace("'", "''")
    safe_sql = (sql or "").replace("'", "''")
    safe_err = (error or "").replace("'", "''")
    wh.execute_write(
        f"INSERT INTO {LOG_TABLE_NAME} "
        f"(TS, MODE, QUESTION, SQL_TEXT, SUCCESS, LATENCY_MS, ERROR) VALUES "
        f"('{ts}', '{mode}', '{safe_q}', '{safe_sql}', "
        f"{1 if success else 0}, {latency_ms:.2f}, '{safe_err}')")


def get_stats(wh: Warehouse, limit: int = 20) -> dict[str, Any]:
    _, total_rows = wh.execute(f"SELECT COUNT(*) FROM {LOG_TABLE_NAME}")
    total = int(total_rows[0][0]) if total_rows else 0
    if total == 0:
        return {"total": 0, "success_rate": None, "p50_ms": None,
                "p95_ms": None, "recent": []}
    _, ok_rows = wh.execute(
        f"SELECT COUNT(*) FROM {LOG_TABLE_NAME} WHERE SUCCESS = 1")
    ok = int(ok_rows[0][0])
    _, lat_rows = wh.execute(
        f"SELECT LATENCY_MS FROM {LOG_TABLE_NAME} WHERE SUCCESS = 1")
    latencies = [float(r[0]) for r in lat_rows]
    cols, recent = wh.execute(
        f"SELECT TS, MODE, QUESTION, SQL_TEXT, SUCCESS, LATENCY_MS, ERROR "
        f"FROM {LOG_TABLE_NAME} ORDER BY ID DESC LIMIT {limit}")
    return {
        "total": total,
        "success_rate": ok / total,
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
        "recent": [dict(zip(cols, r)) for r in recent],
    }
