# ADR 0004: Provider abstraction and evidence-only generation

## Status
Accepted · 2026-11-08

## Context
The service must run in CI without network access while supporting a real Ollama model
or an OpenAI-compatible hosted endpoint. Retrieved passages can contain hostile text,
so evidence must not be allowed to change the model's instructions. Hosted credentials
must remain outside the repository.

## Decision
Keep a provider protocol with stub, Ollama, and hosted implementations. Providers send
structured `Answer` JSON requirements, put instructions before numbered evidence, and
explicitly treat evidence as data rather than instructions. Responses are validated
with Pydantic; malformed output is retried once and then converted to a safe abstaining
fallback. The hosted provider reads `LLM_API_KEY` from the environment only.

## Options considered
One provider would simplify code but would couple CI to a network service and make
deployment changes risky. Free-form text generation would make citations and abstention
unreliable. We therefore chose a shared schema and provider boundary, accepting small
prompt and validation differences between APIs.

## Consequences
CI remains deterministic with the stub provider, while production can select Ollama or
hosted generation through configuration. Provider calls can fail or return malformed
JSON, so callers must handle the safe fallback and citation checks. The relevant code
is in `api/app/providers/llm/`, `api/app/services/validate.py`, and
`api/app/services/grounding.py`.
