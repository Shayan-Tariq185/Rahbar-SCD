#!/usr/bin/env python3
"""Render applyable evaluation/coverage Jobs and a non-networked PVC exporter."""

from __future__ import annotations

import argparse
import re

from eval_bootstrap import ROOT

import yaml

from ragops.evalsuite.io import digest


def pod_spec(image: str, env: dict[str, str], *, exporter: bool = False, with_gate: bool = True) -> dict:
    mounts = [{"name": "results", "mountPath": "/results"}, {"name": "tmp", "mountPath": "/tmp"}]
    volumes = [{"name": "results", "persistentVolumeClaim": {"claimName": "rahbar-eval-results-pvc"}},
               {"name": "tmp", "emptyDir": {}}]
    if not exporter and with_gate:
        mounts.append({"name": "gate", "mountPath": "/config", "readOnly": True})
        volumes.append({"name": "gate", "configMap": {"name": "release-gate"}})
    container = {"name": "exporter" if exporter else "evaluation", "image": image,
                 "imagePullPolicy": "IfNotPresent", "env": [{"name": key, "value": value} for key, value in env.items()],
                 "securityContext": {"readOnlyRootFilesystem": True, "allowPrivilegeEscalation": False,
                                      "capabilities": {"drop": ["ALL"]}},
                 "resources": {"requests": {"cpu": "100m", "memory": "128Mi"},
                               "limits": {"cpu": "1000m", "memory": "512Mi"}}, "volumeMounts": mounts}
    if exporter:
        container["command"] = ["python", "-c", "import time; time.sleep(86400)"]
        container["resources"] = {"requests": {"cpu": "10m", "memory": "32Mi"},
                                  "limits": {"cpu": "100m", "memory": "128Mi"}}
    return {"restartPolicy": "Never", "serviceAccountName": "eval-sa", "automountServiceAccountToken": False,
            "enableServiceLinks": False,
            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001},
            "containers": [container], "volumes": volumes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target", choices=["live", "candidate"], default="live")
    parser.add_argument("--mode", choices=["suite", "coverage"], default="suite")
    parser.add_argument("--baseline-mode", action="store_true")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--embedding-url", default="http://host.minikube.internal:11434")
    parser.add_argument("--judge-model", default="llama3.2:3b")
    parser.add_argument("--bootstrap", action="store_true", help="write non-runnable bootstrap manifests only")
    args = parser.parse_args()
    if not args.bootstrap and not re.search(r"(@sha256:[0-9a-f]{64}$|:[0-9a-f]{12,40}-m2$)", args.image):
        raise ValueError("use an immutable digest or unique source-SHA-m2 image tag")
    if not re.fullmatch(r"[a-z0-9-]+", args.run_id) or args.repeat < 2:
        raise ValueError("safe run ID and repeat>=2 required")
    env = {"EVAL_RUN_ID": args.run_id, "EVAL_MODE": args.mode, "EVAL_REPEAT": str(args.repeat),
           "EVAL_BASELINE_MODE": str(args.baseline_mode).lower(), "RAGOPS_EVAL_IMAGE": args.image,
           "TARGET_API": f"http://{'api' if args.target == 'live' else 'api-candidate'}.rahbar.svc.cluster.local:8000",
           "OLLAMA_URL": args.embedding_url, "JUDGE_MODEL": args.judge_model}
    job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {
        "name": "rahbar-eval" if args.mode == "suite" else "rahbar-coverage", "namespace": "rahbar",
        "annotations": {"rahbar/run-id": args.run_id,
                        "rahbar/resources": "provisional; measure workload before final report"}},
        "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 7200,
                 "template": {"metadata": {"labels": {"app": "rahbar-eval"}},
                              "spec": pod_spec(args.image, env, with_gate=args.mode == "suite")}}}
    path = ROOT / ("k8s/eval-job.yaml" if args.mode == "suite" else "k8s/coverage-job.yaml")
    path.write_text(yaml.safe_dump(job, sort_keys=False), encoding="utf-8")
    exporter = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "eval-results-shell", "namespace": "rahbar",
                "labels": {"app": "rahbar-eval-exporter"}}, "spec": pod_spec(args.image, {}, exporter=True)}
    (ROOT / "k8s/ragops-eval/exporter.yaml").write_text(yaml.safe_dump(exporter, sort_keys=False), encoding="utf-8")
    if not (ROOT / "k8s/ragops-eval/gate-configmap.yaml").exists():
        policy = ROOT / "config/gate.yaml"
        configmap = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {
            "name": "release-gate", "namespace": "rahbar", "annotations": {"rahbar/policy-sha256": digest(policy)}},
            "data": {"gate.yaml": policy.read_text(encoding="utf-8")}}
        (ROOT / "k8s/ragops-eval/gate-configmap.yaml").write_text(yaml.safe_dump(configmap, sort_keys=False), encoding="utf-8")
    print(f"Rendered {path}; image={args.image}; mode={args.mode}; run={args.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
