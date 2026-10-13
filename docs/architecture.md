# Architecture

RubberDuck is a small Python package (`rubberduck/`) with a command line entry point.
The live tool is the `review` command, which a Git pre-commit hook runs. The other
commands (`seed`, `eval`, `fetch-corpus`) exist for the evaluation.

## Review flow

```
git commit
   |
   v
pre-commit hook  ->  rubberduck review
   |
   1. diff.py        read staged .py files: diff, full staged content, changed line numbers
   2. review.py      ask "what should this change do?" in the terminal
   3. sourceview.py  number the file; for files over 400 lines keep only the enclosing function or class
   4. context.py     use jedi "go to definition" on names in changed lines; collect definitions from other files
   5. prompt.py      build one prompt: rules + intent + diff + numbered source + related definitions
   6. llm.py         one Gemini call (temperature 0, JSON schema), retries and fallback models
   7. review.py      print up to 3 questions, then [a]bort or [d]ismiss
   |
   v
commit blocked or allowed
```

Steps 1 to 5 are deterministic Python. Only step 6 uses the model. This keeps the AI part
small and makes every run get the same inputs, which matters for the evaluation.

## Modules

| Module | What it does |
|--------|--------------|
| `cli.py` | Argument parsing and the `review`, `seed`, `eval`, `fetch-corpus` commands. Reads the environment variables. |
| `diff.py` | Runs `git diff --cached` and `git show :path` to get staged files and changed lines. |
| `review.py` | The pre-commit flow: intent prompt, building prompts, printing concerns, abort or dismiss. |
| `sourceview.py` | Numbers source lines and trims large files to the relevant function or class. |
| `context.py` | Cross-file context with `jedi`. Skips the standard library and anything outside the repo. |
| `prompt.py` | The review instructions and prompt assembly. Intent or context can be left out, which the evaluation uses. |
| `llm.py` | Gemini client, JSON parsing, retries on overload or rate limits, fallback models, `.env` loading. |
| `models.py` | Small dataclasses (`Settings`, `Concern`, `StagedFile`, `SeededBug`, `EvalRow`, ...). |
| `mutations.py` | The three bug seeders: variable swap, dictionary key swap, loop collection swap. |
| `evaluate.py` | Finds functions in a corpus, seeds bugs, reviews buggy and clean versions. |
| `metrics.py` | Scores flags against the seeded line and summarizes recall, precision, false positives. |
| `textio.py` | Keeps console output from crashing on characters Windows can't print. |

## Evaluation pieces

- `rubberduck eval` seeds bugs into TinyDB functions and reviews each one under four
  conditions (full, context-only, intent-only, code-only). The function docstring stands
  in for the developer's intent.
- `evaluation/run_intent_eval.py` runs 12 hand-written cases where the bug can only be seen
  if you know the intent, with and without the intent.

Both write CSV files to `results/`.

## Demo tooling

`demo-tools/` holds a reset script that creates an empty `demo/` Git repo and installs the
pre-commit hook, plus the runbook and the prompt used to have an AI agent write the demo program.

## Key decisions

See `docs/adr/` for the reasoning behind the main choices.
