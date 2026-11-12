"""Copilot pipeline: question -> retrieve -> generate SQL -> execute ->
summarize, with every query logged for monitoring.

The pipeline is identical in demo and live mode; only the SQL generator
changes (deterministic DemoTranslator vs. BedrockLLM) and the warehouse
(SQLite vs. Snowflake).
"""
from __future__ import annotations

import time
from typing import Any

from .config import AppConfig
from .llm import BedrockLLM
from .monitoring import get_stats, log_query
from .retrieval import TfidfRetriever
from .schema_docs import all_retrieval_docs
from .translator import DemoTranslator
from .warehouse import TABLE_NAME, Warehouse, build_warehouse

_MONEY_HINTS = ("revenue", "spend", "value", "price", "amount")


def format_value(value: Any, column: str = "") -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        if column.lower() in _MONEY_HINTS or "revenue" in column.lower() \
                or "spend" in column.lower() or "value" in column.lower():
            return f"${value:,.2f}"
        if value == int(value):
            return f"{int(value):,}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def summarize_demo(question: str, columns: list[str],
                   rows: list[tuple]) -> str:
    """Deterministic plain-English summary of a result set (demo mode)."""
    if not rows:
        return "The query ran but returned no rows."
    if len(rows) == 1:
        parts = [f"{c}: {format_value(v, c)}"
                 for c, v in zip(columns, rows[0])]
        return "Result — " + "; ".join(parts) + "."
    lines = []
    for row in rows[:5]:
        label = format_value(row[0], columns[0])
        rest = ", ".join(format_value(v, c)
                         for c, v in zip(columns[1:], row[1:]))
        lines.append(f"{label}: {rest}" if rest else label)
    extra = f" (+{len(rows) - 5} more rows)" if len(rows) > 5 else ""
    return "Top results:\n" + "\n".join(lines) + extra


class Copilot:
    def __init__(self, cfg: AppConfig, warehouse: Warehouse | None = None):
        self.cfg = cfg
        self.mode = cfg.resolve_mode()
        self.warehouse = warehouse or build_warehouse(cfg)
        self.warehouse.create_tables()
        self.retriever = TfidfRetriever(all_retrieval_docs())
        self.countries = self._load_countries()
        if self.mode == "live":
            self.generator: Any = BedrockLLM(cfg.bedrock)
        else:
            self.generator = DemoTranslator(self.retriever, self.countries)

    def _load_countries(self) -> list[str]:
        try:
            _, rows = self.warehouse.execute(
                f"SELECT DISTINCT COUNTRY FROM {TABLE_NAME} "
                f"WHERE COUNTRY IS NOT NULL ORDER BY COUNTRY")
            return [r[0] for r in rows if r[0]]
        except Exception:
            return []

    def ask(self, question: str) -> dict[str, Any]:
        started = time.perf_counter()
        question = (question or "").strip()
        if not question:
            return {"success": False, "mode": self.mode,
                    "question": question, "error": "Empty question."}
        retrieved = self.retriever.retrieve(question, top_k=3)
        if self.mode == "live":
            translation = self.generator.generate_sql(question, retrieved)
        else:
            translation = self.generator.generate(question)
        if translation.error or not translation.sql:
            latency = (time.perf_counter() - started) * 1000
            log_query(self.warehouse, self.mode, question, None, False,
                      latency, translation.error)
            return {"success": False, "mode": self.mode, "question": question,
                    "sql": None, "error": translation.error,
                    "latency_ms": latency,
                    "retrieved": [r["doc"]["text"] for r in retrieved]}
        try:
            columns, rows = self.warehouse.execute(translation.sql)
        except Exception as exc:  # noqa: BLE001 - DB errors are user-visible
            latency = (time.perf_counter() - started) * 1000
            log_query(self.warehouse, self.mode, question, translation.sql,
                      False, latency, str(exc))
            return {"success": False, "mode": self.mode, "question": question,
                    "sql": translation.sql, "error": f"Query failed: {exc}",
                    "latency_ms": latency,
                    "retrieved": [r["doc"]["text"] for r in retrieved]}
        latency = (time.perf_counter() - started) * 1000
        log_query(self.warehouse, self.mode, question, translation.sql,
                  True, latency, None)
        if self.mode == "live":
            answer = self.generator.summarize(
                question, translation.sql, columns, rows)
        else:
            answer = summarize_demo(question, columns, rows)
        return {
            "success": True,
            "mode": self.mode,
            "question": question,
            "sql": translation.sql,
            "columns": columns,
            "rows": [list(r) for r in rows],
            "answer": answer,
            "latency_ms": latency,
            "retrieved": [r["doc"]["text"] for r in retrieved],
            "example_question": translation.example_question,
        }

    def stats(self) -> dict[str, Any]:
        return get_stats(self.warehouse)

    def close(self) -> None:
        self.warehouse.close()
