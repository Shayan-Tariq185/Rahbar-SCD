"""Kubernetes entry point: whole suite then gate, or semantic coverage."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .io import read_json, timestamp, write_json


def command(args: list[str]) -> tuple[int, str]:
    print("+ " + " ".join(args), flush=True)
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    print(completed.stdout, end="", flush=True)
    print(completed.stderr, end="", file=sys.stderr, flush=True)
    return completed.returncode, completed.stdout


def main(*, results_root: Path = Path("/results"), config_root: Path = Path("/config")) -> int:
    if "--help" in sys.argv:
        print("Kubernetes entrypoint; EVAL_RUN_ID, EVAL_MODE, TARGET_API and OLLAMA_URL come from the rendered Job.")
        return 0
    identifier = os.environ["EVAL_RUN_ID"]
    if not identifier or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in identifier):
        raise ValueError("unsafe run ID")
    inputs = results_root / "inputs" / identifier
    output = results_root / "runs" / identifier
    output.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {"run_id": identifier, "started_at": timestamp(), "exit_code": 2,
              "image": os.environ.get("RAGOPS_EVAL_IMAGE"), "suite": None, "decision": None}
    try:
        mode = os.environ.get("EVAL_MODE", "suite")
        if mode == "coverage":
            code, _ = command([sys.executable, "-m", "ragops.coverage", "--golden", str(inputs / "golden.jsonl"),
                               "--live", str(inputs / "live.jsonl"), "--inventory", str(inputs / "inventory.json"),
                               "--config", str(inputs / "coverage.yaml"), "--out", str(output)])
            status["exit_code"] = code if code in (0, 1, 2) else 2
            return int(status["exit_code"])
        if mode != "suite":
            raise ValueError("unknown EVAL_MODE")
        # Snapshot current ConfigMap at process start. A later update cannot change this run's policy.
        shutil.copyfile(config_root / "gate.yaml", output / "gate-at-start.yaml")
        code, log = command([sys.executable, "-m", "ragops.evalsuite", "--target-api", os.environ["TARGET_API"],
                             "--golden", str(inputs / "golden.jsonl"),
                             "--golden-version", os.environ.get("EVAL_GOLDEN_VERSION", "v1"),
                             "--pairs", str(inputs / "pairs.jsonl"),
                             "--inventory", str(inputs / "inventory.json"), "--human-labels", str(inputs / "labels.jsonl"),
                             "--repeat", os.environ.get("EVAL_REPEAT", "2"), "--embedding-url", os.environ["OLLAMA_URL"],
                             "--judge-model", os.environ.get("JUDGE_MODEL", "llama3.2:3b"), "--out", str(output)])
        if code != 0:
            status["exit_code"] = 2
            return 2
        suite_paths = [line.removeprefix("suite_json=") for line in log.splitlines() if line.startswith("suite_json=")]
        if len(suite_paths) != 1:
            raise ValueError("suite did not emit one explicit result path")
        suite_path = Path(suite_paths[0])
        from ragops.gate import measured_suite

        measured_suite(read_json(suite_path))
        status["suite"] = str(suite_path)
        if os.environ.get("EVAL_BASELINE_MODE") == "true":
            print("BASELINE CAPTURE ONLY: no release decision or release authorization", flush=True)
            status["exit_code"] = 0
            return 0
        code, gate_log = command([sys.executable, "-m", "ragops.gate", "--baseline", str(inputs / "baseline.json"),
                                  "--candidate", str(suite_path), "--config", str(output / "gate-at-start.yaml"),
                                  "--current-api", os.environ["TARGET_API"], "--out", str(output)])
        decisions = [line.removeprefix("decision_json=") for line in gate_log.splitlines() if line.startswith("decision_json=")]
        status["decision"] = decisions[0] if len(decisions) == 1 else None
        status["exit_code"] = code if code in (0, 1, 2) else 2
        return int(status["exit_code"])
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        status["error"] = str(exc)
        print(f"Job setup/runtime error: {exc}", file=sys.stderr, flush=True)
        return 2
    finally:
        status["finished_at"] = timestamp()
        write_json(output / "job_exit.json", status)


if __name__ == "__main__":
    raise SystemExit(main())
