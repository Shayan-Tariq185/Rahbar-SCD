# RAHBAR: Grounded RAG on Kubernetes

RAHBAR is a grounded retrieval-augmented generation (RAG) service designed to answer university policy questions from verified documents while strictly citing sources and honestly abstaining when facts are absent. The platform is architected around two decoupled workloads: an ephemeral batch **Indexer Job** that extracts, embeds, and loads vectors into ChromaDB, and a high-availability **FastAPI Service** (3 replicas) that validates questions, checks a Redis semantic cache, retrieves top-$k$ relevant chunks, and produces schema-constrained answers.

---

## Secret Management Workflow

> [!CAUTION]
> **Zero Secrets in Git**: Never commit `.env` files, credentials, tokens, or YAML files containing base64 secrets to Git history (automatic -20 deduction). Base64 encoding is not encryption.

### 1. Creating Real Secrets (CLI Only)
Real credentials (such as `LLM_API_KEY` for hosted LLM providers) are injected directly into the cluster via the command line and never stored in files:

```bash
# 1. Export your secret in your terminal session
export LLM_API_KEY="sk-..."

# 2. Inject it into the rahbar namespace via the Makefile
make secret
```

Under the hood, `make secret` executes:
```bash
kubectl create secret generic rahbar-secret -n rahbar \
  --from-literal=LLM_API_KEY="$LLM_API_KEY" --dry-run=client -o yaml | kubectl apply -f -
```

### 2. The Placeholder Secret (`k8s/base/secret.placeholder.yaml`)
* The repository includes a template file named `k8s/base/secret.placeholder.yaml` containing only the dummy value `REPLACE_ME`.
* **Important**: This placeholder is **never listed** in `kustomization.yaml` so applying manifests will never overwrite your live cluster Secret.

### 3. Graceful Consumption in Pods
The API Deployment consumes the secret as an optional environment variable:
```yaml
env:
  - name: LLM_API_KEY
    valueFrom:
      secretKeyRef:
        name: rahbar-secret
        key: LLM_API_KEY
        optional: true
```
This ensures that local development and CI testing with stubs or local Ollama instances run cleanly even if no secret has been provisioned.
