# Required manual synthetic-question reviews

The eight handwritten questions supplied by the members are separate from these reviews.
Each member must personally inspect four synthetic questions and record an accept/reject
decision plus their own evidence-based explanation. The agent has not approved these
questions on either member's behalf. Facts below are source pointers for review, not
pre-filled human decisions. All page numbers below are physical PDF page numbers.

| Reviewer | ID | Synthetic question | Source to inspect |
| --- | --- | --- | --- |
| Member 2 | q01 | What CGPA places an undergraduate student on academic warning? | Academic Rules 2026 p24, rules 5.4 and 5.5: threshold 2.00 and warning below it |
| Member 2 | q02 | What happens when a student fails to meet the attendance requirement? | Academic Rules 2026 p10, rule 1.22: final-exam ineligibility and F/A |
| Member 2 | q03 | What is the minimum duration of a bachelor's degree? | Academic Rules 2026 p10, rule 1.23: four academic years/eight regular semesters |
| Member 2 | q04 | What does GPA measure? | Academic Rules 2026 p11, rule 2.1: grade averages, SGPA versus CGPA |
| Member 1 | q05 | How is the semester GPA calculated? | Academic Rules 2026 p12, rules 2.4 and 2.5: weighted grade-point formula |
| Member 1 | q06 | What happens if CGPA stays below 2.00 for three consecutive semesters? | Academic Rules 2026 p24, rule 5.6: warning count three and automatic admission closure |
| Member 1 | q07 | What is required before registering for a course? | Academic Rules 2026 p9, rule 1.20: all prerequisites passed |
| Member 1 | q08 | Who may change a student's course load? | Academic Rules 2026 p9, rule 1.18: Head of Department, subject to listed considerations |

Send each review as `qID: accept/reject; your own reason`, with the actual reviewer
identified. A user may relay the partner's actual decisions, explicitly identifying them
as hers. A generic instruction to finish the assignment is not a substitute for reviews.
Questions resembling handwritten ones still require separate review of their synthetic
wording and ground truth; authorship alone does not record that review.

Interactive review is also available in Ubuntu/WSL Bash from the repository directory:

```bash
export RAGOPS_PY=/home/shayantariq/.cache/rahbar-m2-validation-20261125/bin/python
"$RAGOPS_PY" scripts/review_synthetic.py --golden eval/golden.jsonl --reviewer 'Shayan-Tariq185' --limit 4
```

The partner should review q05-q08 herself with her actual identity, skipping earlier rows
if using the interactive tool. Rejects must be resolved before evaluation/freezing. After
eight actual reviews, human faithfulness labeling remains a separate task on real
generated answers and exact retrieved contexts.
