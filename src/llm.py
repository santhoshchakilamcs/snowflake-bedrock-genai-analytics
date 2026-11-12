"""AWS Bedrock LLM layer (live mode only).

Uses boto3 bedrock-runtime to ask a Claude model to write SQL from a
natural-language question, grounded on the schema docs and TF-IDF retrieved
examples. Generated SQL passes through the same read-only guardrail as the
demo translator. A client can be injected for tests; otherwise one is built
from environment credentials (never from files).
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from .schema_docs import EXAMPLES, TABLE_DOC
from .translator import Translation, validate_sql

_SQL_BLOCK_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL
                           | re.IGNORECASE)


def _build_prompt(question: str, retrieved: list[dict]) -> str:
    context = "\n".join(
        f"- {r['doc']['text']}" for r in retrieved)
    few_shot = "\n".join(
        f"Q: {ex['question']}\nSQL: {ex['sql']}"
        for ex in EXAMPLES[:8])
    return (
        "You write read-only SQL for a retail analytics warehouse. "
        "Return ONLY one SQL statement in a fenced sql block, no prose.\n\n"
        f"Schema:\n{TABLE_DOC}\n\n"
        f"Relevant context:\n{context}\n\n"
        f"Examples:\n{few_shot}\n\n"
        f"Question: {question}\nSQL:"
    )


class BedrockLLM:
    def __init__(self, cfg, client: Any = None):
        self.cfg = cfg
        if client is not None:
            self._client = client
        else:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=cfg.region,
                aws_access_key_id=cfg.aws_access_key_id,
                aws_secret_access_key=cfg.aws_secret_access_key,
                aws_session_token=cfg.aws_session_token or None,
            )

    def _invoke(self, prompt: str, max_tokens: int = 1024) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = self._client.invoke_model(
            modelId=self.cfg.model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read())
        parts = payload.get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")

    def generate_sql(self, question: str, retrieved: list[dict]) -> Translation:
        try:
            text = self._invoke(_build_prompt(question, retrieved))
        except Exception as exc:  # noqa: BLE001 - surface as a clean error
            return Translation(
                error=f"Bedrock call failed: {exc}", retrieved=retrieved)
        match = _SQL_BLOCK_RE.search(text)
        sql = match.group(1).strip() if match else text.strip()
        sql = sql.rstrip(";")
        err = validate_sql(sql)
        if err:
            return Translation(error=f"Generated SQL rejected: {err}",
                               retrieved=retrieved)
        return Translation(sql=sql, retrieved=retrieved)

    def summarize(self, question: str, sql: str,
                  columns: list[str], rows: list[tuple]) -> str:
        preview = "\n".join(str(r) for r in rows[:10])
        prompt = (
            "Answer the user's question in one or two plain sentences, "
            "using only the query result below. Give the numbers exactly "
            "as shown.\n\n"
            f"Question: {question}\nSQL: {sql}\n"
            f"Columns: {columns}\nRows:\n{preview}"
        )
        try:
            return self._invoke(prompt, max_tokens=256).strip()
        except Exception as exc:  # noqa: BLE001
            return f"Bedrock summarization failed: {exc}"
