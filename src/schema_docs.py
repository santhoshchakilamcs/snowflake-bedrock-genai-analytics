"""Schema documentation and few-shot examples for retrieval grounding.

These documents are what the TF-IDF retriever searches over. In live mode
they go into the Bedrock prompt as grounding context; in demo mode the
retrieved example pairs drive the deterministic SQL translator (template +
entity substitution). Every example uses the same single-table SQL dialect
described in warehouse.py, so the same SQL runs on SQLite and Snowflake.
"""
from __future__ import annotations

TABLE_DOC = (
    "Table RETAIL_TRANSACTIONS: one row per retail order line from the UCI "
    "Online Retail II dataset, a UK-based online retailer, Dec 2009 to Dec "
    "2011. Columns: INVOICE (order number, text), STOCKCODE (product code, "
    "text), DESCRIPTION (product name, text), QUANTITY (units per line, "
    "integer; negative values are cancellations and returns), INVOICEDATE "
    "(timestamp stored as text 'YYYY-MM-DD HH:MM:SS'), PRICE (unit price, "
    "number), CUSTOMERID (customer number, may be null for guest checkouts), "
    "COUNTRY (customer country, text). Revenue for a line is "
    "QUANTITY * PRICE. Only lines with QUANTITY > 0 count as sales; "
    "negative quantities are returns. Use SUBSTR(INVOICEDATE, 1, 4) for the "
    "year and SUBSTR(INVOICEDATE, 1, 7) for the year-month."
)

COLUMN_DOCS = [
    "INVOICE: the order number. One order has many lines. "
    "COUNT(DISTINCT INVOICE) counts orders.",
    "STOCKCODE: the product code. COUNT(DISTINCT STOCKCODE) counts distinct "
    "products sold.",
    "DESCRIPTION: the product name, e.g. WHITE METAL LANTERN. GROUP BY "
    "DESCRIPTION to rank products.",
    "QUANTITY: units on the order line. Negative values are cancellations "
    "and returns; filter QUANTITY > 0 for sales. SUM(QUANTITY) is units sold.",
    "INVOICEDATE: when the order was placed, stored as text "
    "'YYYY-MM-DD HH:MM:SS'. SUBSTR(INVOICEDATE, 1, 4) is the year, "
    "SUBSTR(INVOICEDATE, 1, 7) is the year-month.",
    "PRICE: unit price in GBP. Line revenue is QUANTITY * PRICE.",
    "CUSTOMERID: the customer number. COUNT(DISTINCT CUSTOMERID) counts "
    "distinct customers. GROUP BY CUSTOMERID to rank customers by spend.",
    "COUNTRY: the customer's country, e.g. United Kingdom, Germany, France. "
    "GROUP BY COUNTRY to compare countries.",
]

# Few-shot examples. Templates use placeholders filled from the question:
# {N} top-N count, {YEAR} 4-digit year, {MONTH} 'YYYY-MM' month,
# {COUNTRY} country name, {KEYWORD} product keyword.
# Each example carries trigger phrases the retriever/translator match on.
EXAMPLES = [
    {
        "question": "What was our total revenue?",
        "sql": ("SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0"),
        "triggers": ["total revenue", "overall revenue", "how much revenue",
                     "total sales"],
    },
    {
        "question": "What was total revenue in {YEAR}?",
        "sql": ("SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
                "SUBSTR(INVOICEDATE, 1, 4) = '{YEAR}'"),
        "triggers": ["revenue in", "total revenue in", "sales in"],
    },
    {
        "question": "What was total revenue in {MONTH}?",
        "sql": ("SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
                "SUBSTR(INVOICEDATE, 1, 7) = '{MONTH}'"),
        "triggers": ["revenue in", "sales in", "revenue for"],
    },
    {
        "question": "What are the top {N} products by revenue?",
        "sql": ("SELECT DESCRIPTION, SUM(QUANTITY * PRICE) AS revenue FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
                "DESCRIPTION IS NOT NULL GROUP BY DESCRIPTION "
                "ORDER BY revenue DESC LIMIT {N}"),
        "triggers": ["top products by revenue", "best products by revenue",
                     "highest revenue products", "products by revenue"],
    },
    {
        "question": "What are the top {N} products by quantity sold?",
        "sql": ("SELECT DESCRIPTION, SUM(QUANTITY) AS units FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
                "DESCRIPTION IS NOT NULL GROUP BY DESCRIPTION "
                "ORDER BY units DESC LIMIT {N}"),
        "triggers": ["top products by quantity", "best-selling products",
                     "most sold products", "products by quantity",
                     "best-selling product"],
    },
    {
        "question": "Which country generated the most revenue?",
        "sql": ("SELECT COUNTRY, SUM(QUANTITY * PRICE) AS revenue FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 GROUP BY COUNTRY "
                "ORDER BY revenue DESC LIMIT 1"),
        "triggers": ["which country", "country generated the most",
                     "most revenue by country", "country with the most"],
    },
    {
        "question": "What are the top {N} countries by revenue?",
        "sql": ("SELECT COUNTRY, SUM(QUANTITY * PRICE) AS revenue FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 GROUP BY COUNTRY "
                "ORDER BY revenue DESC LIMIT {N}"),
        "triggers": ["top countries by revenue", "countries by revenue",
                     "revenue by country"],
    },
    {
        "question": "How many orders did we have?",
        "sql": ("SELECT COUNT(DISTINCT INVOICE) AS orders FROM "
                "RETAIL_TRANSACTIONS"),
        "triggers": ["how many orders", "number of orders", "order count",
                     "total orders"],
    },
    {
        "question": "How many distinct customers do we have?",
        "sql": ("SELECT COUNT(DISTINCT CUSTOMERID) AS customers FROM "
                "RETAIL_TRANSACTIONS"),
        "triggers": ["how many customers", "distinct customers",
                     "number of customers"],
    },
    {
        "question": "How many distinct products do we sell?",
        "sql": ("SELECT COUNT(DISTINCT STOCKCODE) AS products FROM "
                "RETAIL_TRANSACTIONS"),
        "triggers": ["how many products", "distinct products",
                     "number of products"],
    },
    {
        "question": "What was the average order value?",
        "sql": ("SELECT SUM(QUANTITY * PRICE) / COUNT(DISTINCT INVOICE) "
                "AS avg_order_value FROM RETAIL_TRANSACTIONS "
                "WHERE QUANTITY > 0"),
        "triggers": ["average order value", "avg order value",
                     "mean order value"],
    },
    {
        "question": "Who are our top {N} customers by total spend?",
        "sql": ("SELECT CUSTOMERID, SUM(QUANTITY * PRICE) AS spend FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
                "CUSTOMERID IS NOT NULL GROUP BY CUSTOMERID "
                "ORDER BY spend DESC LIMIT {N}"),
        "triggers": ["top customers", "best customers", "customers by spend",
                     "highest spending customers"],
    },
    {
        "question": "What was revenue from {COUNTRY}?",
        "sql": ("SELECT SUM(QUANTITY * PRICE) AS revenue FROM "
                "RETAIL_TRANSACTIONS WHERE QUANTITY > 0 AND "
                "COUNTRY = '{COUNTRY}'"),
        "triggers": ["revenue from", "sales from", "revenue in"],
    },
    {
        "question": "How many orders came from {COUNTRY}?",
        "sql": ("SELECT COUNT(DISTINCT INVOICE) AS orders FROM "
                "RETAIL_TRANSACTIONS WHERE COUNTRY = '{COUNTRY}'"),
        "triggers": ["how many orders from", "orders from", "orders in"],
    },
    {
        "question": "Which month had the highest revenue?",
        "sql": ("SELECT SUBSTR(INVOICEDATE, 1, 7) AS month, "
                "SUM(QUANTITY * PRICE) AS revenue FROM RETAIL_TRANSACTIONS "
                "WHERE QUANTITY > 0 GROUP BY month ORDER BY revenue DESC "
                "LIMIT 1"),
        "triggers": ["which month", "best month", "highest revenue month",
                     "month with the highest revenue"],
    },
    {
        "question": "Which products contain {KEYWORD}?",
        "sql": ("SELECT DISTINCT DESCRIPTION FROM RETAIL_TRANSACTIONS "
                "WHERE DESCRIPTION LIKE '%{KEYWORD}%' LIMIT 20"),
        "triggers": ["products contain", "products with", "find products",
                     "search products"],
    },
]


def all_retrieval_docs() -> list[dict]:
    """Documents for TF-IDF: table doc, column docs, example questions."""
    docs = [{"kind": "table", "text": TABLE_DOC}]
    for c in COLUMN_DOCS:
        docs.append({"kind": "column", "text": c})
    for ex in EXAMPLES:
        docs.append({
            "kind": "example",
            "text": ex["question"] + " " + " ".join(ex["triggers"]),
            "example": ex,
        })
    return docs
