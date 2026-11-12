"""Eval set: 20 natural-language questions with hand-written reference SQL.

Reference SQL uses only the shared single-table dialect (SUBSTR for dates),
so the same statements run on SQLite (demo) and Snowflake (live).
Correctness = the copilot's generated SQL executes AND returns the same
result as the reference SQL (floats compared with a small tolerance, rows
compared as multisets so ORDER BY ties do not fail the check).
"""
from __future__ import annotations

EVAL_QUESTIONS = [
    {
        "question": "What was our total revenue?",
        "reference_sql": (
            "SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0"),
    },
    {
        "question": "What was total revenue in 2010?",
        "reference_sql": (
            "SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "SUBSTR(INVOICEDATE, 1, 4) = '2010'"),
    },
    {
        "question": "What was total revenue in December 2010?",
        "reference_sql": (
            "SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "SUBSTR(INVOICEDATE, 1, 7) = '2010-12'"),
    },
    {
        "question": "What are the top 5 products by revenue?",
        "reference_sql": (
            "SELECT DESCRIPTION, SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "DESCRIPTION IS NOT NULL GROUP BY DESCRIPTION "
            "ORDER BY revenue DESC LIMIT 5"),
    },
    {
        "question": "What are the top 10 products by quantity sold?",
        "reference_sql": (
            "SELECT DESCRIPTION, SUM(QUANTITY) AS units FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "DESCRIPTION IS NOT NULL GROUP BY DESCRIPTION "
            "ORDER BY units DESC LIMIT 10"),
    },
    {
        "question": "Which country generated the most revenue?",
        "reference_sql": (
            "SELECT COUNTRY, SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 GROUP BY COUNTRY "
            "ORDER BY revenue DESC LIMIT 1"),
    },
    {
        "question": "What are the top 5 countries by revenue?",
        "reference_sql": (
            "SELECT COUNTRY, SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 GROUP BY COUNTRY "
            "ORDER BY revenue DESC LIMIT 5"),
    },
    {
        "question": "How many orders did we have?",
        "reference_sql": (
            "SELECT COUNT(DISTINCT INVOICE) AS orders FROM "
            "RETAIL_TRANSACTIONS"),
    },
    {
        "question": "How many orders were there in 2011?",
        "reference_sql": (
            "SELECT COUNT(DISTINCT INVOICE) AS orders FROM "
            "RETAIL_TRANSACTIONS WHERE SUBSTR(INVOICEDATE, 1, 4) = '2011'"),
    },
    {
        "question": "How many distinct customers do we have?",
        "reference_sql": (
            "SELECT COUNT(DISTINCT CUSTOMERID) AS customers FROM "
            "RETAIL_TRANSACTIONS"),
    },
    {
        "question": "How many distinct products do we sell?",
        "reference_sql": (
            "SELECT COUNT(DISTINCT STOCKCODE) AS products FROM "
            "RETAIL_TRANSACTIONS"),
    },
    {
        "question": "What was the average order value?",
        "reference_sql": (
            "SELECT SUM(QUANTITY * PRICE) / COUNT(DISTINCT INVOICE) "
            "AS avg_order_value FROM RETAIL_TRANSACTIONS WHERE QUANTITY > 0"),
    },
    {
        "question": "Who are our top 5 customers by total spend?",
        "reference_sql": (
            "SELECT CUSTOMERID, SUM(QUANTITY * PRICE) AS spend FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "CUSTOMERID IS NOT NULL GROUP BY CUSTOMERID "
            "ORDER BY spend DESC LIMIT 5"),
    },
    {
        "question": "What was revenue from the United Kingdom?",
        "reference_sql": (
            "SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "COUNTRY = 'United Kingdom'"),
    },
    {
        "question": "What was revenue from Germany in 2010?",
        "reference_sql": (
            "SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "COUNTRY = 'Germany' AND SUBSTR(INVOICEDATE, 1, 4) = '2010'"),
    },
    {
        "question": "What is the best-selling product by quantity?",
        "reference_sql": (
            "SELECT DESCRIPTION, SUM(QUANTITY) AS units FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "DESCRIPTION IS NOT NULL GROUP BY DESCRIPTION "
            "ORDER BY units DESC LIMIT 1"),
    },
    {
        "question": "What was total revenue in November 2011?",
        "reference_sql": (
            "SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "SUBSTR(INVOICEDATE, 1, 7) = '2011-11'"),
    },
    {
        "question": "How many orders came from France?",
        "reference_sql": (
            "SELECT COUNT(DISTINCT INVOICE) AS orders FROM "
            "RETAIL_TRANSACTIONS WHERE COUNTRY = 'France'"),
    },
    {
        "question": "What are the top 3 products by revenue in 2011?",
        "reference_sql": (
            "SELECT DESCRIPTION, SUM(QUANTITY * PRICE) AS revenue FROM "
            "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
            "DESCRIPTION IS NOT NULL AND SUBSTR(INVOICEDATE, 1, 4) = '2011' "
            "GROUP BY DESCRIPTION ORDER BY revenue DESC LIMIT 3"),
    },
    {
        "question": "Which month had the highest revenue?",
        "reference_sql": (
            "SELECT SUBSTR(INVOICEDATE, 1, 7) AS month, "
            "SUM(QUANTITY * PRICE) AS revenue FROM RETAIL_TRANSACTIONS "
            "WHERE QUANTITY > 0 GROUP BY month ORDER BY revenue DESC "
            "LIMIT 1"),
    },
]
