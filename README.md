# Snowflake + Bedrock GenAI Analytics Copilot

A natural-language analytics copilot: ask a question in English, the system
retrieves schema context, writes SQL, runs it on the warehouse, and answers
with results and a chart. Every query is logged, and a monitoring view
tracks query volume, success rate, and latency.

**This is a personal project.** It demonstrates the Snowflake + AWS Bedrock
integration and the end-to-end pipeline (data platform → model/AI
application → production monitoring → business outcome). It does **not**
claim production Snowflake or Bedrock experience, and no number in this
README is a production number.

## What was actually verified (demo mode, local run)

All numbers below were measured locally in **demo mode** on 2026-11-11:
SQLite warehouse + deterministic SQL translator, no Snowflake or Bedrock
credentials. Demo-mode numbers are **not** Snowflake/Bedrock numbers.

- **Dataset:** UCI Online Retail II (real retail transactions, UK online
  retailer). 1,067,371 rows, Dec 1, 2009 – Dec 9, 2011, 43 countries,
  5,942 customers, 5,305 products.
- **Eval set:** 20 natural-language questions with hand-written reference
  SQL. Correctness = generated SQL executes AND returns the same result
  as the reference SQL (float tolerance 1e-6 relative, rows compared as
  multisets). Full results: `eval/results_demo.json`.
- **Execution success: 20/20 (100%)** — every generated SQL statement ran.
- **Answer correctness: 20/20 (100%)** — every answer matched the
  reference SQL result.
- **Latency (end-to-end: retrieve + generate + execute): p50 357.1 ms,
  p95 841.9 ms** on this VM against the 1M-row SQLite warehouse.
  (A repeat run gave p50 360.5 ms / p95 900.3 ms; latency varies a
  little run to run, the 20/20 results do not.)
- **Tests: 33 passed** (`./run.sh test`).
- **Spot-checked answers (demo mode, real data):** total revenue
  $20,814,292.00; 53,628 orders; average order value $496.24; best month
  2011-11 at $1,509,496.33; top product by revenue REGENCY CAKESTAND
  3 TIER at $344,563.25; top country United Kingdom at $17,712,675.21.

## Two modes

| | Demo mode (default) | Live mode |
|---|---|---|
| Warehouse | Local SQLite (`data/warehouse.db`) | Real Snowflake (`snowflake-connector-python`) |
| SQL generation | Deterministic pattern-based translator + TF-IDF retrieval (stdlib) | AWS Bedrock LLM via boto3 (`bedrock-runtime`) |
| Data | Same UCI Online Retail II dataset | Same dataset, loaded into Snowflake |
| SQL dialect | One shared dialect (SUBSTR dates, SUM/COUNT/AVG, LIMIT) that runs unchanged on both backends | Same |

The pipeline (ask → retrieve → generate → guardrail → execute →
summarize → log) is identical in both modes; only the warehouse and the
SQL generator change. The UI always shows which mode is active.

## What live mode needs (not included)

Live mode has never been run here — this VM has no Snowflake account and
no AWS credentials. To run it, supply **only via environment variables**
(never hardcoded, never committed):

- A Snowflake trial account: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
  `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, plus optional
  `SNOWFLAKE_ROLE`, `SNOWFLAKE_DATABASE` (default `GENAI_ANALYTICS`),
  `SNOWFLAKE_SCHEMA` (default `PUBLIC`).
- AWS credentials with Bedrock access: `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (optional), `AWS_REGION`
  (default `us-east-1`), `BEDROCK_MODEL_ID` (default
  `anthropic.claude-3-sonnet-20240229-v1:0`).
- Set `APP_MODE=live` (default `auto` switches to live only when all
  required variables are present; otherwise it stays in demo mode).

Live-mode eval numbers do not exist yet — run `./run.sh eval` with
`APP_MODE=live` to produce `eval/results_live.json` before quoting any
Bedrock accuracy or latency figure.

## How to run

```bash
./run.sh           # web UI on http://127.0.0.1:8003 (ingests on first run)
./run.sh ingest    # download/load the UCI dataset into the warehouse
./run.sh eval      # run the 20-question eval set, print + save metrics
./run.sh test      # pytest suite
```

Python 3.10+; dependencies in `requirements.txt` (installed into the
project `.venv` by default; `run.sh` uses `.venv/bin/python` when it
exists, otherwise `python3`). First run downloads UCI Online Retail II
(~45 MB xlsx) into `data/` and caches a parsed CSV there for fast
re-runs. Data files, databases, and `.env` are gitignored; the repo is
code only.

## Architecture

```
src/
  config.py      env-only config, demo/live mode resolution
  warehouse.py   one SQL surface over SQLite (demo) / Snowflake (live)
  ingest.py      UCI Online Retail II -> RETAIL_TRANSACTIONS (both sheets)
  schema_docs.py table/column docs + few-shot question->SQL examples
  retrieval.py   stdlib TF-IDF over the schema docs
  translator.py  demo-mode deterministic SQL generator + read-only guardrail
  llm.py         Bedrock LLM SQL generation + summarization (live mode)
  copilot.py     pipeline: retrieve -> generate -> execute -> summarize -> log
  monitoring.py  query log (QUERY_LOG table) + success/latency stats
  evalset.py     20 eval questions with hand-written reference SQL
  app.py         FastAPI service + web UI
static/index.html  minimal UI: ask, SQL, results, CSS bar chart, monitoring
eval/run_eval.py   eval runner (writes eval/results_<mode>.json)
tests/           pytest suite (translator, retrieval, warehouse, copilot,
                 API, mocked Bedrock client, ingest helpers)
```

Design notes:

- **One SQL dialect.** `INVOICEDATE` is stored as TEXT/VARCHAR
  `'YYYY-MM-DD HH:MM:SS'` in both backends, and generated SQL uses only
  functions present in both dialects. That is a deliberate portability
  choice so the demo-tested SQL runs unchanged on Snowflake.
- **Read-only guardrail.** Every generated statement (demo or Bedrock)
  must be a single SELECT over `RETAIL_TRANSACTIONS`; DROP/DELETE/
  INSERT/UPDATE, multi-statement input, and other tables are rejected.
- **Monitoring is the pipeline, not an afterthought.** Every question —
  answered or not — is logged with latency and outcome, and the
  monitoring view reads the same log table.
- **Revenue means sales only.** Reference and generated SQL filter
  `QUANTITY > 0`; negative quantities are cancellations/returns.

## Honest limits

- Demo-mode eval numbers measure the deterministic translator, not an
  LLM. Do not present them as Bedrock accuracy.
- No Snowflake or Bedrock production experience is claimed. The live
  code path is written and unit-tested with a mocked boto3 client, but
  it has not run against real Snowflake or Bedrock.
- The dataset is 2009–2011 retail data; answers describe that data, not
  any live business.
