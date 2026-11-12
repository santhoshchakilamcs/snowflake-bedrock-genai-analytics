"""Tests for the Bedrock LLM layer with a mocked boto3 client.

No AWS credentials or network are used here; the client is injected.
"""
import json

from src.config import BedrockConfig
from src.llm import BedrockLLM


class _FakeBody:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()


class _FakeClient:
    def __init__(self, text):
        self.text = text

    def invoke_model(self, **kwargs):
        return {"body": _FakeBody(
            {"content": [{"type": "text", "text": self.text}]})}


class _FailingClient:
    def invoke_model(self, **kwargs):
        raise RuntimeError("network down")


def _llm(client):
    return BedrockLLM(BedrockConfig.from_env(), client=client)


def test_generate_sql_extracts_fenced_block():
    llm = _llm(_FakeClient(
        "```sql\nSELECT SUM(QUANTITY * PRICE) AS revenue FROM "
        "RETAIL_TRANSACTIONS WHERE QUANTITY > 0\n```"))
    t = llm.generate_sql("What was our total revenue?", [])
    assert t.sql is not None
    assert t.error is None
    assert "SUM(QUANTITY * PRICE)" in t.sql


def test_generate_sql_rejects_dangerous_output():
    llm = _llm(_FakeClient("```sql\nDROP TABLE RETAIL_TRANSACTIONS\n```"))
    t = llm.generate_sql("drop everything", [])
    assert t.sql is None
    assert t.error


def test_generate_sql_client_failure():
    llm = _llm(_FailingClient())
    t = llm.generate_sql("What was our total revenue?", [])
    assert t.sql is None
    assert "Bedrock call failed" in t.error


def test_summarize_returns_text():
    llm = _llm(_FakeClient("Total revenue was $87.50."))
    out = llm.summarize("What was our total revenue?", "SELECT 1",
                        ["revenue"], [(87.5,)])
    assert "87.50" in out
