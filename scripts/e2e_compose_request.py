"""
Lab 9: minimal end-to-end check against a running compose stack.
Usage (after `docker compose up -d`):
  pip install httpx  # optional; falls back to urllib

  python scripts/e2e_compose_request.py
  python scripts/e2e_compose_request.py --base-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid


def post_json(url: str, payload: dict, timeout: float = 600.0) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, raw


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = p.parse_args()
    base = args.base_url.rstrip("/")

    code, health = post_json(f"{base}/health", {}, timeout=30.0)
    if code != 200:
        print("health failed", code, health, file=sys.stderr)
        return 1
    print("health:", health)

    tid = str(uuid.uuid4())
    body = {
        "message": "Write a very short outline for a blog on markdown headings for developers.",
        "thread_id": tid,
    }
    code, text = post_json(f"{base}/chat", body, timeout=900.0)
    print("chat status:", code)
    print("chat body:", text[:2000])
    if code != 200:
        return 1
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return 1
    if obj.get("status") not in ("interrupted_awaiting_hitl", "completed", "blocked"):
        print("unexpected response status field", file=sys.stderr)
        return 1
    if not (obj.get("final_answer") or "").strip() and obj.get("status") != "blocked":
        print("empty final_answer", file=sys.stderr)
        return 1
    print("PASS: agent returned a structured ChatResponse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
