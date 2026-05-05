#!/usr/bin/env python3
"""
Lab 10: CI-ready evaluation gate.

- Reads credentials from environment (GROQ_API_KEY required).
- Runs lab7_eval.py headlessly; no interactive input.
- Loads eval_thresholds.json (committed thresholds).
- Writes ci_eval_results.json with each metric, score, threshold, pass/fail.
- Exit code 0 if all gates pass, 1 if any fail (or subprocess / I/O error).

Environment:
  GROQ_API_KEY     required
  CI_EVAL_LIMIT    optional, default 5 (rows from test_dataset.json)
  BWA_LLM_GUARD    optional (passed through if set before lab7 runs)
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THRESHOLDS_PATH = ROOT / "eval_thresholds.json"
RAW_PATH = ROOT / "ci_eval_raw.json"
REPORT_PATH = ROOT / "ci_eval_results.json"


def _is_bad_number(x: object) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return True
    return False


def main() -> int:
    if not os.getenv("GROQ_API_KEY", "").strip():
        print(
            "run_eval: missing GROQ_API_KEY in environment "
            "(locally: export/set GROQ_API_KEY; GitHub: repo Settings → Secrets → Actions).",
            file=sys.stderr,
        )
        return 1

    if not THRESHOLDS_PATH.is_file():
        print(f"run_eval: missing {THRESHOLDS_PATH}", file=sys.stderr)
        return 1

    spec = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    metrics_spec = spec.get("metrics") or {}
    if len(metrics_spec) < 2:
        print("run_eval: eval_thresholds.json must define at least two metrics", file=sys.stderr)
        return 1

    limit = os.getenv("CI_EVAL_LIMIT", "5").strip() or "5"
    cmd = [
        sys.executable,
        str(ROOT / "lab7_eval.py"),
        "--limit",
        limit,
        "--output",
        str(RAW_PATH),
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        print("run_eval: lab7_eval.py failed", file=sys.stderr)
        return 1

    if not RAW_PATH.is_file():
        print(f"run_eval: missing output {RAW_PATH}", file=sys.stderr)
        return 1

    data = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    summary = data.get("summary") or {}

    gate_results = []
    all_pass = True
    for name, mspec in metrics_spec.items():
        thr = float(mspec["min"])
        score = summary.get(name)
        bad = _is_bad_number(score)
        try:
            num = float(score) if not bad else float("nan")
        except (TypeError, ValueError):
            num = float("nan")
            bad = True
        passed = (not bad) and num >= thr
        if not passed:
            all_pass = False
        gate_results.append(
            {
                "metric": name,
                "score": None if bad else num,
                "threshold_min": thr,
                "pass": passed,
                "rationale": mspec.get("rationale", ""),
            }
        )

    report = {
        "overall_pass": all_pass,
        "ci_eval_limit": limit,
        "summary_from_lab7": summary,
        "gates": gate_results,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"overall_pass": all_pass, "report": str(REPORT_PATH)}, indent=2))
    if not all_pass:
        failed = [g for g in gate_results if not g["pass"]]
        print("run_eval: gate failure(s):", file=sys.stderr)
        for g in failed:
            print(
                f"  - {g['metric']}: score={g['score']} need min={g['threshold_min']}",
                file=sys.stderr,
            )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
