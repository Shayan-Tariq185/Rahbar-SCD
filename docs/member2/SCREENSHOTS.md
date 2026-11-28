# Screenshot commands

Use **Windows PowerShell**. First set the working directory:

```powershell
Set-Location -LiteralPath 'C:\Users\PC\Desktop\5th Semester\Software Construction and Development\Assignment-2\tmp\integrated-evidence'
```

Save captures in `report\appendix\`. Capture the command and its actual output in the full terminal window. If output needs several screens, save consecutive captures with the same label and suffixes `-1`, `-2`. The completed commands below read existing evidence; they do not rerun the experiments.

## A1 document verification

```powershell
Get-Content 'eval\results\verification-b-20261128\verification.md' -Encoding UTF8
```

Save as `A1-verification-1.png` etc. Include all four checks and document decisions.

## A2 and F2 ingestion zero embeddings

```powershell
wsl -d Ubuntu-22.04 --exec kubectl get job ragops-ingest-1795876857-21933 -n rahbar
wsl -d Ubuntu-22.04 --exec kubectl logs job/ragops-ingest-1795876857-21933 -n rahbar --tail=27
```

Save as `A2-zero-embeddings.png`.

## B1 evaluation both complete passes

```powershell
Get-Content 'eval\results\baseline-a-20261128\eval-20261128t145145z-7222c9f3\suite-20261128T145225Z-3a48878c.md' -Encoding UTF8
```

Save as `B1-evaluation-1.png` etc. Include module, component, E2E and repeat deltas.

## E1 coverage before expansion

```powershell
Get-Content 'eval\results\coverage-before-20261128\eval-20261128t171041z-a30234b6\coverage-20261128T171048Z-58751684.md' -Encoding UTF8
```

Save as `E1-coverage-before.png`. The measured 67.5 percent is an intentional recorded below-floor outcome.

## E2 coverage after expansion

```powershell
Get-Content 'eval\results\coverage-after-20261128\eval-20261128t171133z-2f0ecbbb\coverage-20261128T171140Z-60a562ea.md' -Encoding UTF8
```

Save as `E2-coverage-after.png`. It shows 97.5 percent with unchanged cutoff and floor.

## D1 full compact trace

```powershell
wsl -d Ubuntu-22.04 --exec python3 scripts/trace_show.py 10ded7228b9846ba839aef575ccb330f --traces-dir traces --json
```

Save consecutive complete captures as `D1-full-trace-1.png` etc. This real compact request used the application ASGI route inside the deployed API image with isolated A+B configuration.

## D2 reconstruct exact evidence and prompt

```powershell
wsl -d Ubuntu-22.04 --exec python3 scripts/trace_show.py 10ded7228b9846ba839aef575ccb330f --traces-dir traces
```

Save as `D2-reconstruction-1.png` etc. Keep both original evidence and outgoing prompt readable.

## D4 injection handling

```powershell
wsl -d Ubuntu-22.04 --exec python3 scripts/trace_show.py b17c227460ce48bc8886ddea7446161d --traces-dir traces
```

Save the guardrail action and actual 50 GB answer in `D4-injection-1.png` etc. The source is a synthetic test policy. A separate compact trace shows a limitation: section metadata can retain malicious wording, even after body sanitation.

## Remaining captures

C gates and F cluster/configuration and rollout/undo commands will be added with their actual completed Job names and result paths. These sections are still in progress; no successful outcome is claimed yet.
