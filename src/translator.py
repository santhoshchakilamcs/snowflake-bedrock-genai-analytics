"""Demo-mode deterministic SQL translator.

Pipeline: TF-IDF retrieval picks the best few-shot example, entities
(top-N, year, month, country, keyword) are extracted from the question,
the example template is filled, and any additional entity filters the
template does not already express are composed into the WHERE clause.
Every generated statement passes a read-only guardrail before it is run.

This is NOT an LLM. It is a transparent, deterministic stand-in so the
identical pipeline (ask -> retrieve -> generate SQL -> execute -> answer)
runs end-to-end without Bedrock credentials. Live mode swaps this out for
the Bedrock LLM layer (llm.py) behind the same interface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .retrieval import TfidfRetriever
from .schema_docs import EXAMPLES

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

_FORBIDDEN = re.compile(
    r"\b(drop|delete|insert|update|alter|create|truncate|grant|revoke|"
    r"merge|call|exec|execute)\b|--|/\*|;",
    re.IGNORECASE,
)
_FROM_RE = re.compile(r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
_JOIN_RE = re.compile(r"\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)

ALLOWED_TABLE = "RETAIL_TRANSACTIONS"


@dataclass
class Entities:
    n: int = 5
    year: str | None = None
    month: str | None = None  # 'YYYY-MM'
    country: str | None = None
    keyword: str | None = None


@dataclass
class Translation:
    sql: str | None = None
    error: str | None = None
    retrieved: list[dict] = field(default_factory=list)
    example_question: str | None = None


def extract_entities(question: str, countries: list[str]) -> Entities:
    q = question.lower()
    ent = Entities()

    m = re.search(r"top\s+(\d+)", q)
    if m:
        ent.n = int(m.group(1))
    elif re.search(r"best-selling product\b(?!s)", q) or \
            re.search(r"\bwhich\b.*\bproduct\b", q):
        ent.n = 1

    ym = re.search(r"\b(20\d{2}|19\d{2})\b", q)
    if ym:
        ent.year = ym.group(1)

    for name, num in MONTHS.items():
        if re.search(rf"\b{name}\b", q):
            if ent.year:
                ent.month = f"{ent.year}-{num}"
            break

    for country in countries:
        if country.lower() in q:
            ent.country = country
            break

    km = re.search(r"(?:contain|contains|with|named|called)\s+([a-z][a-z ]+)",
                   q)
    if km:
        ent.keyword = km.group(1).strip().strip("?.")

    return ent


def _placeholders(sql: str) -> set[str]:
    return set(re.findall(r"\{([A-Z]+)\}", sql))


def _fill_template(sql: str, ent: Entities) -> str | None:
    """Fill placeholders; return None if a required entity is missing."""
    needed = _placeholders(sql)
    values: dict[str, str] = {"N": str(ent.n)}
    if "YEAR" in needed:
        if not ent.year:
            return None
        values["YEAR"] = ent.year
    if "MONTH" in needed:
        if not ent.month:
            return None
        values["MONTH"] = ent.month
    if "COUNTRY" in needed:
        if not ent.country:
            return None
        values["COUNTRY"] = ent.country.replace("'", "''")
    if "KEYWORD" in needed:
        if not ent.keyword:
            return None
        values["KEYWORD"] = re.sub(
            r"[^a-zA-Z ]", "", ent.keyword).strip().replace("'", "''")
    return sql.format(**values)


def _inject_filter(sql: str, condition: str) -> str:
    """Add one AND/WHERE condition before GROUP BY / ORDER BY / LIMIT."""
    anchor = re.search(r"\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b",
                       sql, re.IGNORECASE)
    clause = (" AND " if " WHERE " in sql.upper() else " WHERE ") + condition
    if anchor:
        return sql[:anchor.start()] + clause + sql[anchor.start():]
    return sql + clause


def _compose_extra_filters(sql: str, ent: Entities) -> str:
    upper = sql.upper()
    if ent.month and "SUBSTR(INVOICEDATE, 1, 7)" not in upper:
        sql = _inject_filter(
            sql, f"SUBSTR(INVOICEDATE, 1, 7) = '{ent.month}'")
        upper = sql.upper()
    if ent.year and "SUBSTR(INVOICEDATE, 1, 4)" not in upper:
        sql = _inject_filter(
            sql, f"SUBSTR(INVOICEDATE, 1, 4) = '{ent.year}'")
        upper = sql.upper()
    if ent.country and "COUNTRY =" not in upper:
        sql = _inject_filter(
            sql, f"COUNTRY = '{ent.country.replace(chr(39), chr(39) * 2)}'")
    return sql


def validate_sql(sql: str) -> str | None:
    """Read-only guardrail. Returns an error string, or None if valid."""
    s = sql.strip()
    if not s:
        return "Empty SQL."
    if not re.match(r"(?i)select\b", s):
        return "Only SELECT statements are allowed."
    if _FORBIDDEN.search(s):
        return ("Blocked: statement contains a forbidden keyword or "
                "multiple statements.")
    tables = _FROM_RE.findall(s) + _JOIN_RE.findall(s)
    if not tables:
        return "No table referenced."
    for t in tables:
        if t.upper() != ALLOWED_TABLE:
            return f"Table {t} is not allowed."
    return None


class DemoTranslator:
    """Deterministic translator used in demo mode."""

    def __init__(self, retriever: TfidfRetriever, countries: list[str]):
        self.retriever = retriever
        self.countries = countries

    def generate(self, question: str) -> Translation:
        retrieved = self.retriever.retrieve(question, top_k=3)
        ent = extract_entities(question, self.countries)
        ql = question.lower()
        # Trigger matching ignores standalone numbers so "top 3 products"
        # matches the "top products" trigger phrases.
        q_trig = re.sub(r"\s+", " ",
                        re.sub(r"\b\d+\b", "", ql)).strip()

        # Score examples: trigger overlap dominates, then placeholder
        # specificity (month/year/country/N present), then TF-IDF cosine.
        best = None
        best_score = -1.0
        cosine_by_example: dict[int, float] = {}
        for r in retrieved:
            doc = r["doc"]
            if doc.get("kind") == "example":
                cosine_by_example[id(doc["example"])] = r["score"]
        for ex in EXAMPLES:
            triggers = sum(1 for t in ex["triggers"] if t in q_trig)
            filled = _fill_template(ex["sql"], ent)
            if filled is None:
                continue  # required entity missing; example not eligible
            specificity = 0.0
            if "{MONTH}" in ex["sql"] and ent.month:
                specificity += 1.0
            if "{YEAR}" in ex["sql"] and ent.year:
                specificity += 1.0
            if "{COUNTRY}" in ex["sql"] and ent.country:
                specificity += 1.0
            if "{N}" in ex["sql"]:
                specificity += 1.0 if re.search(r"top\s+\d+", ql) else 0.5
            cosine = cosine_by_example.get(id(ex), 0.0)
            score = 3.0 * triggers + 2.0 * specificity + cosine
            if triggers == 0 and cosine < 0.30:
                continue
            if score > best_score:
                best_score = score
                best = (ex, filled)

        if best is None:
            return Translation(
                error=("I cannot turn that question into a safe query over "
                       "the retail transactions table. Try asking about "
                       "revenue, top products or countries, order counts, "
                       "customers, or average order value."),
                retrieved=retrieved,
            )

        ex, sql = best
        sql = _compose_extra_filters(sql, ent)
        err = validate_sql(sql)
        if err:
            return Translation(error=err, retrieved=retrieved)
        return Translation(sql=sql, retrieved=retrieved,
                           example_question=ex["question"])
