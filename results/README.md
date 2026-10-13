# Evaluation results

| File | What it is | How to reproduce |
|------|------------|------------------|
| `intent-eval-results.csv` | Intent benchmark: 12 hand-written cases, each reviewed buggy and clean, with and without the intent (48 rows) | `python -m evaluation.run_intent_eval --pause 4` |
| `tinydb-eval.csv` | Seeded-bug evaluation on TinyDB under four conditions (written when you re-run it) | `rubberduck fetch-corpus` then `rubberduck eval --repo corpus/tinydb --max-per-class 5 --pause 4 --yes` |

Each row is one review. `hit` is true only when a flag points at the exact bugged line.
`flagged` on a clean row is a false alarm.

## Note on the TinyDB numbers

The TinyDB results in the README, the slides, and the report (14/15 bugs caught in every
condition) come from the run shown in the Week 7 presentation. That run was made with an
older default output path (`rubberduck-eval.csv`, which was gitignored at the time), so the
raw rows were not kept. The commands above regenerate the same evaluation; because the model
is called live, a re-run can differ by a bug or a false alarm.
