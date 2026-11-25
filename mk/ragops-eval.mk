# M1 integrates with: include mk/ragops-eval.mk
# RAGOPS_PY can be a Windows interpreter or the existing WSL .venv/bin/python.
RAGOPS_PY ?= $(BIN)/python

.PHONY: ragops-eval-test ragops-eval-lint
ragops-eval-test: ## run M2 offline contracts and A02 evaluator tests
	"$(RAGOPS_PY)" -B -m pytest -q tests/ragops/evaluation eval/test_run_eval.py

ragops-eval-lint: ## lint and type-check M2 evaluation interfaces
	"$(RAGOPS_PY)" -m ruff check ragops tests/ragops/evaluation
	"$(RAGOPS_PY)" -m mypy ragops
