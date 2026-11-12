"""Eval runner: ask each eval question through the copilot and compare the
returned result against the hand-written reference SQL.

Metrics reported (with the mode stated next to each number):
- execution success rate: generated SQL ran without error
- answer correctness rate: generated result matches the reference result
- latency p50 / p95 (end-to-end: retrieve + generate + execute)

Results are written to eval/results_<mode>.json and printed. Run with:
    python -m eval.run_eval            (demo mode, default)
    APP_MODE=live python -m eval.run_eval
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.config import AppConfig  # noqa: E402
from src.copilot import Copilot  # noqa: E402
from src.evalset import EVAL_QUESTIONS  # noqa: E402
from src.monitoring import _percentile  # noqa: E402
from src.warehouse import build_warehouse  # noqa: E402


def _cells_match(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            return a == b
        return abs(fa - fb) <= 1e-6 * max(1.0, abs(fb))
    return a == b


def _rows_match(got: list[list], expected: list[tuple]) -> bool:
    if len(got) != len(expected):
        return False
    norm_got = sorted(tuple(r) for r in got)
    norm_exp = sorted(tuple(r) for r in expected)
    return all(
        len(gr) == len(er) and all(_cells_match(g, e) for g, e in zip(gr, er))
        for gr, er in zip(norm_got, norm_exp))


def run_eval(cfg: AppConfig) -> dict:
    wh = build_warehouse(cfg)
    try:
        _, rows = wh.execute("SELECT COUNT(*) FROM RETAIL_TRANSACTIONS")
        if not rows or rows[0][0] == 0:
            from src.ingest import ingest

            ingest(cfg, wh)
    finally:
        pass  # keep the warehouse open for the copilot below
    copilot = Copilot(cfg, warehouse=wh)
    results = []
    latencies = []
    try:
        for item in EVAL_QUESTIONS:
            q = item["question"]
            answer = copilot.ask(q)
            executed = bool(answer.get("success"))
            matched = False
            expected = None
            if executed:
                _, expected = wh.execute(item["reference_sql"])
                matched = _rows_match(answer["rows"], expected)
            latencies.append(answer.get("latency_ms") or 0.0)
            results.append({
                "question": q,
                "sql": answer.get("sql"),
                "executed": executed,
                "matched": matched,
                "latency_ms": answer.get("latency_ms"),
                "error": answer.get("error"),
            })
    finally:
        copilot.close()

    n = len(results)
    summary = {
        "mode": copilot.mode,
        "n": n,
        "execution_success": sum(1 for r in results if r["executed"]),
        "correct": sum(1 for r in results if r["matched"]),
        "execution_success_rate": sum(1 for r in results if r["executed"]) / n,
        "correctness_rate": sum(1 for r in results if r["matched"]) / n,
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "results": results,
    }
    return summary


def main() -> None:
    cfg = AppConfig.from_env()
    summary = run_eval(cfg)
    out_path = os.path.join(
        cfg.project_root, "eval", f"results_{summary['mode']}.json")
    with open(out_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Mode: {summary['mode']}")
    print(f"Questions: {summary['n']}")
    print(f"Execution success: {summary['execution_success']}/"
          f"{summary['n']} = {summary['execution_success_rate']:.1%}")
    print(f"Correct answers: {summary['correct']}/{summary['n']} = "
          f"{summary['correctness_rate']:.1%}")
    print(f"Latency p50: {summary['latency_p50_ms']:.1f} ms, "
          f"p95: {summary['latency_p95_ms']:.1f} ms")
    for r in summary["results"]:
        mark = "OK " if r["matched"] else ("EXEC " if r["executed"] else "FAIL")
        print(f"  [{mark}] {r['question']}"
              + (f"  -- {r['error']}" if r["error"] else ""))
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
