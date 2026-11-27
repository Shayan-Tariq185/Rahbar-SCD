#!/usr/bin/env python3
"""Verify a rejected candidate did not alter the live Deployment template/revision."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval_bootstrap import ROOT  # noqa: F401

from ragops.evalsuite.io import read_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    before, after = read_json(args.before), read_json(args.after)
    for value in (before, after):
        if value.get("kind") != "Deployment" or value["metadata"]["name"] != "api":
            raise ValueError("expected actual live Deployment api JSON")
        for container in value["spec"]["template"]["spec"]["containers"]:
            for env in container.get("env", []):
                if any(word in env["name"].upper() for word in ("KEY", "TOKEN", "PASSWORD")) and "value" in env:
                    raise ValueError("literal secret in captured Deployment; use secretKeyRef and recapture")
    same_template = before["spec"]["template"] == after["spec"]["template"]
    revisions = [v["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision") for v in (before, after)]
    if any(not revision for revision in revisions):
        raise ValueError("both Deployment snapshots must contain an observed rollout revision")
    same_revision = revisions[0] == revisions[1]
    print(f"live PodTemplate unchanged: {same_template}; Deployment revision unchanged: {same_revision}")
    print("This checks the Deployment snapshot; release values must be pinned explicitly in its PodTemplate.")
    return 0 if same_template and same_revision else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"rollout check error: {exc}", file=sys.stderr)
        raise SystemExit(2)
