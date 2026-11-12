#!/usr/bin/env bash
# Snowflake + Bedrock GenAI Analytics Copilot
#   ./run.sh           start the web UI on http://127.0.0.1:8003
#   ./run.sh ingest    download/load the UCI dataset into the warehouse
#   ./run.sh eval      run the 20-question eval set and print metrics
#   ./run.sh test      run the pytest suite
set -e
cd "$(dirname "$0")"
if [ -d .venv ]; then
  PY=.venv/bin/python
else
  PY=python3
fi
case "${1:-serve}" in
  serve)
    exec $PY -m uvicorn src.app:app --host 127.0.0.1 --port 8003
    ;;
  ingest)
    exec $PY -m src.ingest
    ;;
  eval)
    exec $PY -m eval.run_eval
    ;;
  test)
    exec $PY -m pytest tests -v
    ;;
  *)
    echo "Usage: $0 [serve|ingest|eval|test]"
    exit 1
    ;;
esac
