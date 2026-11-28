#!/usr/bin/env python3
"""Lightweight query load driver for F5 API/Chroma resource measurement."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DEFAULT_QUESTIONS = [
    "What CGPA puts a student on academic warning?",
    "What is the minimum attendance requirement to sit the final exam?",
    "How are tuition fees refunded when dropping a course?",
    "How many textbooks can an undergraduate borrow from the library?",
    "What items are prohibited inside examination halls?",
]


def _send_one(url: str, question: str) -> tuple[int, float]:
    t0 = time.perf_counter()
    data = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/ask",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        resp.read()
        return resp.status, (time.perf_counter() - t0) * 1000.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send steady query load for F5 resource sampling.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--count", type=int, default=30, help="Total requests to send")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent worker threads")
    args = parser.parse_args(argv)

    questions = [DEFAULT_QUESTIONS[i % len(DEFAULT_QUESTIONS)] for i in range(args.count)]
    ok = 0
    failed = 0
    latencies: list[float] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for future in [pool.submit(_send_one, args.url, q) for q in questions]:
            try:
                status, ms = future.result()
                latencies.append(ms)
                if 200 <= status < 300:
                    ok += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                print(f"request failed: {exc}", file=sys.stderr)

    print(
        json.dumps(
            {
                "url": args.url,
                "total": args.count,
                "ok": ok,
                "failed": failed,
                "mean_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            },
            indent=2,
        )
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
