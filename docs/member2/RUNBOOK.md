# M2.0 reproducible commands and screenshot status

The user authorized Codex to run Git, WSL, installations, Docker/Kubernetes and feature
branch pushes. Screenshots remain manual. M2.0 requires no appendix screenshot; later
screenshot commands will reference actual Jobs, results and traces.

## Environment

PowerShell repository: `C:\Users\PC\Desktop\5th Semester\Software Construction and Development\Assignment-2`.
WSL distro: Ubuntu-22.04. Ubuntu/WSL Bash working directory:

```bash
cd '/mnt/c/Users/PC/Desktop/5th Semester/Software Construction and Development/Assignment-2'
```

The old `.venv/bin/python` points to missing `/usr/bin/python3.12` and was not replaced.
The nested `.venv/ragops-env` was a partial setup attempt. The final validation environment
is in the Linux user cache to avoid slow Windows-mounted file operations. A temporary
`/tmp` environment did not persist between sessions.

## Setup (executed by Codex)

Same Bash terminal, repository root:

```bash
uv venv --python python3.12 /home/shayantariq/.cache/rahbar-m2-validation-20261125
uv pip install --python /home/shayantariq/.cache/rahbar-m2-validation-20261125/bin/python -r api/requirements-dev.txt -r indexer/requirements-dev.txt -r eval/requirements-dev.txt types-PyYAML types-requests
```

Do not recreate an active environment merely for screenshots. CPython 3.12.16 and all
declared requirement files were used. PROGRESS.md records actual validation outcomes.

## Offline checks

Same terminal/directory:

```bash
make test VENV=/home/shayantariq/.cache/rahbar-m2-validation-20261125
make lint VENV=/home/shayantariq/.cache/rahbar-m2-validation-20261125
make -f Makefile -f mk/ragops-eval.mk ragops-eval-test ragops-eval-lint VENV=/home/shayantariq/.cache/rahbar-m2-validation-20261125
(cd api && /home/shayantariq/.cache/rahbar-m2-validation-20261125/bin/python -m pytest -q --cov=app --cov-fail-under=60 --cov-report=term-missing)
```

Expected shape: passing tests, API coverage >=60%, Ruff passes, mypy reports no errors.
The OCR test skips if tesseract/poppler are absent; this does not prove OCR execution.
Root Makefile is unchanged; loading the member fragment explicitly tests integration.

## Partner integration

Review H0-CONTRACTS.md, M1-ADAPTER-REVIEW.md and config/schemas/h0.schema.json.
The unmerged partner branch was reviewed at a recorded SHA; no partner files changed.
After M1 reconciles their branch with dev and both members agree the contract, M1 can run
in their checkout, Ubuntu/WSL Bash, repository root:

```bash
git apply --check docs/member2/INTEGRATION.patch
git apply docs/member2/INTEGRATION.patch
```

The patch adds a Makefile include and a shared-contract link. It was source-context
checked, not applied here. If M1 already has section 8, incorporate the agreed link there
instead of duplicating that section. Do not force patch application.

## Git status and review

Codex created feat/m2-evaluation-contracts from current origin/dev and set the user-provided
repository-local identity. The pre-existing scripts/check_submission.py edit, assignment
PDFs, root guides and output artifacts are excluded from the M2 commit. No git add .

Reproducible review/push commands, Bash at repository root:

```bash
git status --short --branch
git diff --check
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "feat(ragops): propose member 2 evaluation contracts and offline harness"
git push -u origin feat/m2-evaluation-contracts
```

Only explicit M2 files are staged. PR target is dev; draft PR/remote CI are separate from
H0 acceptance and Kubernetes readiness. No merge or direct main push is authorized by this phase.
