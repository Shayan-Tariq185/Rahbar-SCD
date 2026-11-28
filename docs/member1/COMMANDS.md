# Member 1 Verified Repository Facts & Commands

## Verified A02 Repository Configuration
- **Namespace**: `rahbar` (`k8s/base/namespace.yaml`)
- **API Route**: `POST /api/ask` (accepts `{"question": "..."}` 3–500 chars; `api/app/routes/ask.py`)
- **Health Probes**: `GET /healthz` (liveness), `GET /readyz` (readiness: Redis, Chroma count > 0, `EMBED_MODEL` pin)
- **Metrics Route**: `GET /metrics` (Prometheus text format on port `8000`)
- **Service Ports (`k8s/base/services.yaml`)**:
  - `api`: `ClusterIP` port `8000` -> `targetPort: 8000` (selector `app: rahbar-api`)
  - `ui`: `ClusterIP` port `8080` -> `targetPort: 8080` (selector `app: rahbar-ui`)
  - `chroma`: `ClusterIP` port `8000` -> `targetPort: 8000` (selector `app: rahbar-chroma`)
  - `redis`: `ClusterIP` port `6379` -> `targetPort: 6379` (selector `app: rahbar-redis`)
- **ConfigMap & Secret Names**: `rahbar-config`, `rahbar-secret` (key `LLM_API_KEY`)
- **Docker Build Contexts**:
  - API: `docker build -t rahbar-api:<TAG> api`
  - UI: `docker build -t rahbar-ui:<TAG> ui`
  - Indexer: `docker build -f indexer/Dockerfile --build-arg CORPUS_SRC=<DIR> -t rahbar-indexer:<TAG> .` (repo root context)
- **Python Environment**: Python `3.12` (`Makefile`: `make install`, `make test`, `make lint`, `make dev`, `make check`)

## Current A02 Smoke-Test & Offline Checks
```bash
# Offline unit tests (A02)
make test
# Or directly:
cd api && pytest -v
cd indexer && pytest -v

# Offline runtime tests (A03 Member 1)
python -m pytest tests/ragops/runtime -v

# Lint & static checks
make lint

# Kustomize manifest validation
kubectl kustomize k8s/overlays/dev > /dev/null
kubectl kustomize k8s/ragops-runtime > /dev/null
```

## Cluster Startup Order (M1.0–M1.4)
1. Ensure namespace, ConfigMap, Secrets, PVCs, Chroma StatefulSet, Redis, and Services are applied (`kubectl apply -k k8s/ragops-runtime`).
2. Wait for `statefulset/chroma` and `deploy/redis` to become Ready.
3. Deploy helper pod `kubectl apply -f k8s/tools/runtime-shell.yaml` and wait for Ready.
4. Run writer ingestion (`bash scripts/ingest_job.sh --collection rahbar_a --batch-dir <BATCH_A_DIR>`) BEFORE expecting `deploy/api` `/readyz` to pass (because `/readyz` verifies non-empty collection and matching `EMBED_MODEL`).
5. Watch `deploy/api` rollout (`kubectl rollout status deploy/api -n rahbar`).

## Host Ollama Reachability Check (Windows + Minikube)
```bash
# Inside WSL / cluster pod:
curl -fsS http://host.minikube.internal:11434/api/tags
```
If `host.minikube.internal` resolves to a different gateway IP than `192.168.49.1/32` in your Minikube driver, update the `ipBlock` CIDR in `k8s/base/networkpolicy.yaml` / `k8s/ragops-runtime/networkpolicy-runtime.yaml`.
