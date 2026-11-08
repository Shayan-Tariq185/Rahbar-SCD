# AI usage

| Tool | What it wrote or shaped | What we changed afterwards, and why |
| --- | --- | --- |
| Copilot SDK in VS Code | Helped inspect the starter contracts, implement Track B pipeline/API/evaluation code, and draft tests and documentation. | We ran repository tests, Ruff, mypy, the real local indexer, Chroma retrieval checks, and the evaluation gate; we retained only changes supported by those results. |
| Ubuntu shell and project test tools | Executed `make test`, `make lint`, the indexer, Chroma queries, and `eval/run_eval.py`. | We used observed chunk counts, scores, and gate output rather than inventing measurements. |
