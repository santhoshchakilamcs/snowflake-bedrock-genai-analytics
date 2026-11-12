"""Tests for the demo-mode SQL translator and the read-only guardrail."""
from src.evalset import EVAL_QUESTIONS
from src.retrieval import TfidfRetriever
from src.schema_docs import all_retrieval_docs
from src.translator import DemoTranslator, validate_sql
from tests.conftest import COUNTRIES


def _translator():
    return DemoTranslator(TfidfRetriever(all_retrieval_docs()), COUNTRIES)


def test_all_eval_questions_translate():
    """Every eval question must produce valid, guardrail-passing SQL."""
    tr = _translator()
    for item in EVAL_QUESTIONS:
        t = tr.generate(item["question"])
        assert t.sql is not None, f"no SQL for {item['question']!r}: {t.error}"
        assert t.error is None
        assert validate_sql(t.sql) is None


def test_december_revenue_uses_month():
    tr = _translator()
    t = tr.generate("What was total revenue in December 2010?")
    assert t.sql is not None
    assert "2010-12" in t.sql


def test_top_products_with_year():
    tr = _translator()
    t = tr.generate("What are the top 3 products by revenue in 2011?")
    assert t.sql is not None
    assert "LIMIT 3" in t.sql
    assert "'2011'" in t.sql


def test_country_and_year_compose():
    tr = _translator()
    t = tr.generate("What was revenue from Germany in 2010?")
    assert t.sql is not None
    assert "Germany" in t.sql
    assert "'2010'" in t.sql


def test_best_selling_is_top_one():
    tr = _translator()
    t = tr.generate("What is the best-selling product by quantity?")
    assert t.sql is not None
    assert "LIMIT 1" in t.sql


def test_unanswerable_question():
    tr = _translator()
    t = tr.generate("What is the weather like in Paris tomorrow?")
    assert t.sql is None
    assert t.error


def test_guardrail_rejects_dangerous_sql():
    assert validate_sql("DROP TABLE RETAIL_TRANSACTIONS") is not None
    assert validate_sql("DELETE FROM RETAIL_TRANSACTIONS") is not None
    assert validate_sql("SELECT * FROM RETAIL_TRANSACTIONS; DROP TABLE X") is not None
    assert validate_sql("INSERT INTO RETAIL_TRANSACTIONS VALUES (1)") is not None
    assert validate_sql("SELECT * FROM OTHER_TABLE") is not None
    assert validate_sql("UPDATE RETAIL_TRANSACTIONS SET PRICE = 0") is not None


def test_guardrail_accepts_valid_sql():
    assert validate_sql(
        "SELECT SUM(QUANTITY * PRICE) FROM RETAIL_TRANSACTIONS "
        "WHERE QUANTITY > 0") is None
    assert validate_sql(
        "SELECT COUNTRY, SUM(QUANTITY * PRICE) AS revenue FROM "
        "RETAIL_TRANSACTIONS GROUP BY COUNTRY ORDER BY revenue DESC "
        "LIMIT 5") is None
