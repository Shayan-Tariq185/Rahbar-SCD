# Local environment preparation on 2026-11-28

Deadline preparation was authorized while Member 1 fixes the runtime integration.
These are environment checks, not Assignment 03 experiment results.

## Observed state

- Started Docker Desktop successfully; Docker server version 29.9.3 was read.
- Started the existing `minikube` profile without deleting cluster data.
- Minikube reports host, kubelet and API server Running; kubeconfig is configured.
- `kubectl get nodes` reports the existing Kubernetes v1.37.0 control-plane node Ready.
- Existing A02 API, Chroma, Redis and UI pods resumed. Existing indexing/CronJob
  workloads are present; they are not new Assignment 03 ingestion evidence.
- WSL reported 7.6 GiB total / approximately 7.0 GiB available before cluster startup.
- Ollama was already running on Windows. `nomic-embed-text:latest` is installed,
  with dimension 768 and exact digest
  `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`.
- Started downloading `llama3.2:3b`, the configured judge model. Completion must be
  checked from `/api/tags`; the pull being started is not proof it is installed.

## Verified model connection

The minikube node could not connect to `http://host.minikube.internal:11434`.
It could read Ollama tags at `http://host.docker.internal:11434` instead.
A separate check from the existing API pod resolved host.docker.internal to
192.168.65.254 and received HTTP 200 from `/api/tags`.

The local provisional coverage configuration now uses that observed endpoint and
embedding digest. It remains unfrozen. The M2 evaluation egress policy now permits
that observed /32 address on TCP 11434; this edited policy has not yet been applied.
DNS/host addresses must be rechecked for another machine or cluster.

In Ubuntu/WSL Bash at the repository root, use these actual local values:

```bash
export RAGOPS_PY=/home/shayantariq/.cache/rahbar-m2-validation-20261125/bin/python
export OLLAMA_URL=http://host.docker.internal:11434
```

Evaluation wrappers must use `--context minikube`, and image loading must use
`--profile minikube`, for this existing cluster. The old runbook's rahbar-a03 name
is an example profile, not this observed local profile. Pass the verified model URL
to the evaluation Job with `--embedding-url "$OLLAMA_URL"`.

No A03 baseline was frozen, no new A/B corpus was ingested, no candidate was released,
and no evaluation/gate/coverage score was generated during this preparation.
