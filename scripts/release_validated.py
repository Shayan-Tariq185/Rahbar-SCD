#!/usr/bin/env python3
"""Revalidate bound measurements and atomically roll out the measured candidate."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from eval_bootstrap import ROOT  # noqa: F401
from ragops.evalsuite.clients import HttpApiClient
from ragops.evalsuite.io import digest, read_config, read_json, run_id, timestamp, write_json
from ragops.gate import decide


def kubectl(namespace: str, *args: str) -> str:
    return subprocess.run(["kubectl", "-n", namespace, *args], check=True,
                          text=True, capture_output=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment", default="api")
    parser.add_argument("--candidate-deployment", default="api-candidate")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--decision", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--current-api", required=True)
    parser.add_argument("--namespace", "-n", default="rahbar")
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    original = read_json(args.decision)
    for key, path in (("baseline_sha256", args.baseline), ("candidate_sha256", args.suite),
                      ("policy_sha256", args.policy), ("golden_sha256", args.golden)):
        if original.get(key) != digest(path):
            raise ValueError(f"decision input binding differs: {key}")
    if original.get("release_authorized") is not True or original.get("test_only"):
        raise ValueError("decision does not authorize a measured release")
    identity = asdict(HttpApiClient(args.current_api).identity())
    fresh = decide(read_json(args.baseline), read_json(args.suite), read_config(args.policy),
                   baseline_hash=digest(args.baseline), candidate_hash=digest(args.suite),
                   policy_hash=digest(args.policy), current_identity=identity)
    if not fresh["release_authorized"] or fresh["candidate_identity"] != original.get("candidate_identity"):
        raise ValueError("fresh gate/identity does not authorize this release")
    if identity["collection"] != args.candidate:
        raise ValueError("candidate collection differs")
    candidate = json.loads(kubectl(args.namespace, "get", "deployment", args.candidate_deployment, "-o", "json"))
    container = next(c for c in candidate["spec"]["template"]["spec"]["containers"] if c["name"] == "api")
    if container["image"] != identity["api_image"]:
        raise ValueError("deployed candidate image differs from measured identity")
    if container["image"].endswith((":dev", ":latest")):
        raise ValueError("candidate image must have an immutable source tag/digest")
    # Copy the effective candidate configuration in the same PodTemplate mutation.
    config = json.loads(identity["config_json"])
    pins = {"CHROMA_COLLECTION": identity["collection"], "EMBED_MODEL": identity["embedding"]["model"],
            "EMBED_VERSION": identity["embedding"]["digest"], "API_IMAGE": identity["api_image"],
            "TOP_K": str(config["top_k"]), "TEMPERATURE": str(config["temperature"]),
            "RELEVANCE_FLOOR": str(config["relevance_floor"]),
            "CACHE_THRESHOLD": str(config["cache_threshold"]), "PROMPT_VERSION": str(config["prompt_version"])}
    env = [row for row in container.get("env", []) if row["name"] not in pins]
    env.extend({"name": name, "value": value} for name, value in pins.items())
    patch = {"spec": {"strategy": {"type": "RollingUpdate", "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1}},
                      "template": {"spec": {"containers": [{"name": "api", "image": container["image"],
                                                            "env": env, "envFrom": container.get("envFrom", [])}]}}}}
    before = json.loads(kubectl(args.namespace, "get", "deployment", args.deployment, "-o", "json"))
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / run_id("release")
    patch_path = stem.with_suffix(".patch.json")
    write_json(patch_path, patch)
    audit = {"timestamp": timestamp(), "decision_sha256": digest(args.decision), "fresh_decision": fresh,
             "deployment": args.deployment, "namespace": args.namespace, "dry_run": args.dry_run,
             "rollback_revision": before["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision"),
             "before_template": before["spec"]["template"], "patch": patch}
    if args.dry_run:
        print("DRY-RUN: fresh measured release validation passed; no cluster mutation")
    else:
        print(kubectl(args.namespace, "patch", "deployment", args.deployment,
                      "--type", "strategic", "--patch-file", str(patch_path)), end="")
        print(kubectl(args.namespace, "rollout", "status", f"deployment/{args.deployment}", "--timeout=300s"), end="")
        after = json.loads(kubectl(args.namespace, "get", "deployment", args.deployment, "-o", "json"))
        audit["after_template"] = after["spec"]["template"]
        audit["new_revision"] = after["metadata"]["annotations"]["deployment.kubernetes.io/revision"]
    write_json(stem.with_suffix(".json"), audit)
    print(f"Release audit: {stem.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
