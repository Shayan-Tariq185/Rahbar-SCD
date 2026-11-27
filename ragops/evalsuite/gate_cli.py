#!/usr/bin/env python3
"""Apply the gate to real measured results and a freshly read target identity."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


from ragops.evalsuite.io import digest, read_config, read_json, run_id, schema_check, write_json
from ragops.gate import decide


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--current-api", help="read live target identity immediately before gating")
    source.add_argument("--current-identity", type=Path, help="recent captured identity; release helper must recheck it")
    args = parser.parse_args()
    if args.current_api:
        from ragops.evalsuite.clients import HttpApiClient

        from dataclasses import asdict
        identity = asdict(HttpApiClient(args.current_api).identity())
    else:
        identity = read_json(args.current_identity)
    result = decide(read_json(args.baseline), read_json(args.candidate), read_config(args.config),
                    baseline_hash=digest(args.baseline), candidate_hash=digest(args.candidate),
                    policy_hash=digest(args.config), current_identity=identity)
    # A captured file may be used for diagnosis, never as the sole fresh release check.
    if not args.current_api:
        result["release_authorized"] = False
        result["identity_check"] = "captured file only; no fresh runtime check"
    schema_check("gate_decision", result)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = run_id("gate")
    write_json(args.out / (stem + ".json"), result)
    lines = [f"# Gate {result['decision'].upper()}", "", "| Metric | Baseline | Candidate | Threshold | Pass |",
             "| --- | ---: | ---: | ---: | --- |"]
    lines += [f"| {r['metric']} | {r['baseline']:.6g} | {r['candidate']:.6g} | {r['threshold']:.6g} | {r['passed']} |" for r in result["checks"]]
    lines += ["", f"Release authorized: {result['release_authorized']}"]
    (args.out / (stem + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"decision_json={args.out / (stem + '.json')}")
    return int(result["exit_code"])


def entrypoint() -> int:
    try:
        return main()
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"gate setup/runtime error: {exc}", file=sys.stderr)
        return 2
