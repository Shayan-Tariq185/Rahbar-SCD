# ADR 0004: LLM Provider Architecture, Secret Governance, and Student PII Protection

## Status
Accepted · 2026-11-07

## Context
A question-answering system operating over university academic regulations inevitably handles queries containing Personally Identifiable Information (PII) — student names, roll numbers, academic probation status, disciplinary records, and financial aid inquiries. Furthermore, commercial LLM APIs require authorization keys that pose catastrophic financial and security risks if leaked into version control.

## Decision
1. **Local Self-Hosted Provider by Default (`ollama-host`)**:
   - The production cluster connects to a self-hosted Ollama instance running `llama3.2:3b` on the host workstation network (`host.minikube.internal:11434`).
   - NetworkPolicy explicitly restricts egress so student prompts never leave the local security perimeter.
2. **Hosted Fallback & Zero-Retention Policy (`hosted`)**:
   - For environments lacking GPU acceleration, a cloud-hosted provider interface is supported (`HostedProvider`), requiring endpoints with zero-data-retention terms.
3. **Strict PII Redaction in Observability**:
   - Application structured logs (`api/app/logjson.py`) log request metadata (`request_id`, `top_k`, `chunk_ids`, `latency`, `confidence`), but **never log raw prompt bodies or student identity tokens**.
4. **Zero-Secret Kubernetes Governance**:
   - API keys are injected via `kubectl create secret generic rahbar-secret` (`make secret`) and consumed as optional environment variables. No secrets or base64 files are committed to Git history.

## Consequences
- *Positive*: Full compliance with university data privacy norms and zero risk of secret compromise in GitHub repositories.
- *Trade-off*: Local inference latency is hardware-dependent (CPU vs GPU).

