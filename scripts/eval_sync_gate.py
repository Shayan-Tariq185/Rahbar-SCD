#!/usr/bin/env python3
"""Render the gate ConfigMap from its exact source file, optionally applying it."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from eval_bootstrap import ROOT

import yaml

from ragops.evalsuite.io import digest, read_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    read_config(args.config)
    manifest = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {
        "name": "release-gate", "namespace": "rahbar", "annotations": {"rahbar/policy-sha256": digest(args.config)}},
        "data": {"gate.yaml": args.config.read_text(encoding="utf-8")}}
    path = ROOT / "k8s/ragops-eval/gate-configmap.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"Rendered release-gate; policy SHA-256={digest(args.config)}")
    if args.apply:
        print(f"+ kubectl apply -f {path}", flush=True)
        subprocess.run(["kubectl", "apply", "-f", str(path)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
