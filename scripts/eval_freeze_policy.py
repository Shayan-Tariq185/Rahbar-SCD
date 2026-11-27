#!/usr/bin/env python3
"""Bind an original justified release policy to a real baseline before candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

from eval_bootstrap import ROOT  # noqa: F401

import yaml

from ragops.evalsuite.io import digest, finite, read_config, read_json
from ragops.gate import measured_suite


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/gate.yaml"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--latency-headroom", type=float, default=1.25)
    parser.add_argument("--rationale", required=True)
    args = parser.parse_args()
    baseline = read_json(args.baseline)
    measured_suite(baseline)
    headroom = finite(args.latency_headroom, minimum=1)
    policy = read_config(args.config)
    if args.out.exists() and read_config(args.out).get("frozen"):
        raise ValueError("original frozen policy already exists; do not retune it after candidate outcomes")
    latency = max(finite(run["e2e"]["latency_p95_ms"]["value"], minimum=0) for run in baseline["runs"])
    policy.update({"frozen": True, "baseline_sha256": digest(args.baseline), "policy_mode": "release",
                   "max_p95_latency_ms": latency * headroom,
                   "rationale": args.rationale + f" Baseline worst repeat p95={latency:.6g} ms; headroom={headroom}. "
                   "Two repeats do not establish a statistical confidence interval; preserve original quality floors."})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
    print(f"Frozen original policy {args.out}; baseline SHA-256 {policy['baseline_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"policy freeze error: {exc}")
        raise SystemExit(2)
