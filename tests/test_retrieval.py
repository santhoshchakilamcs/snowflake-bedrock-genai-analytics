"""Tests for the TF-IDF retriever."""
from src.retrieval import TfidfRetriever
from src.schema_docs import all_retrieval_docs


def test_retrieval_finds_revenue_example():
    r = TfidfRetriever(all_retrieval_docs())
    top = r.retrieve("What was our total revenue?", top_k=3)
    assert top, "expected at least one retrieved doc"
    assert all(0.0 < t["score"] <= 1.0 for t in top)
    texts = " ".join(t["doc"]["text"] for t in top).lower()
    assert "revenue" in texts


def test_retrieval_finds_country_example():
    r = TfidfRetriever(all_retrieval_docs())
    top = r.retrieve("Which country generated the most revenue?", top_k=3)
    assert top
    kinds = [t["doc"].get("kind") for t in top]
    assert "example" in kinds


def test_retrieval_empty_query():
    r = TfidfRetriever(all_retrieval_docs())
    assert r.retrieve("", top_k=3) == []
    assert r.retrieve("   ", top_k=3) == []


def test_retrieval_scores_sorted():
    r = TfidfRetriever(all_retrieval_docs())
    top = r.retrieve("top products by quantity sold", top_k=5)
    scores = [t["score"] for t in top]
    assert scores == sorted(scores, reverse=True)
