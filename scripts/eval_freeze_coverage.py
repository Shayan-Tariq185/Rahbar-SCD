#!/usr/bin/env python3
"""Freeze a human-justified coverage policy against an actual calibration artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from eval_bootstrap import ROOT  # noqa: F401

import yaml

from ragops.evalsuite.io import digest, finite, read_config, read_json, schema_check


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--cutoff", required=True, type=float)
    parser.add_argument("--floor", required=True, type=float)
    parser.add_argument("--rationale", required=True)
    args = parser.parse_args()
    report = read_json(args.calibration)
    schema_check("coverage_report", report)
    if report.get("mode") != "calibration" or report.get("provenance") != "real" or report.get("errors"):
        raise ValueError("requires actual error-free calibration, not a fixture or final result")
    if args.out.exists():
        raise ValueError("refusing to overwrite an existing coverage policy")
    config = read_config(args.config)
    if config.get("frozen") or report["config_sha256"] != digest(args.config):
        raise ValueError("calibration must use this unchanged provisional configuration")
    if not args.rationale.strip():
        raise ValueError("explain inspected near-match/non-match examples and the aggregate coverage target")
    if config["embedding"] != report["embedding"]:
        # A resolved :latest suffix is equivalent only with the same pinned digest and dimension.
        configured = config["embedding"]
        resolved = report["embedding"]
        if (resolved["model"] not in {configured["model"], configured["model"] + ":latest"}
                or any(configured[key] != resolved[key] for key in ("digest", "dimension"))):
            raise ValueError("calibration embedding identity differs from the configured pin")
    config.update({"frozen": True, "similarity_cutoff": finite(args.cutoff, minimum=-1, maximum=1),
                   "coverage_floor": finite(args.floor, minimum=0, maximum=1),
                   "rationale": args.rationale.strip(), "calibration_sha256": digest(args.calibration),
                   "live_sha256": report["live_sha256"]})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        yaml.safe_dump(config, stream, sort_keys=False)
    print(f"Frozen {args.out}; use the same live set and policy for v1 and v2")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"coverage policy error: {exc}")
        raise SystemExit(2)
