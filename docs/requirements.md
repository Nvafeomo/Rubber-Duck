# Requirements and Acceptance Criteria

## Goal

Catch subtle logic bugs in staged Python code before it is committed, by checking the
code against what the developer says the change is supposed to do.

The target bugs are code that runs without errors but does the wrong thing:

- **Wrong variable**: using a different in-scope variable than the one that was meant.
- **Wrong dictionary key**: reading a valid but incorrect field.
- **Wrong loop collection**: looping over a different list or dict than the one that was meant.

## Users

Solo developers and small teams that do not have a dedicated reviewer, working in a
local Git repository.

## Functional requirements

| ID | Requirement |
|----|-------------|
| FR1 | RubberDuck runs automatically from a Git pre-commit hook. |
| FR2 | It reviews only staged `.py` files. If nothing Python is staged, it exits quietly. |
| FR3 | Before reviewing, it asks the developer "what should this change do?" (or takes the intent from `--intent` or `RUBBERDUCK_INTENT`). |
| FR4 | The model receives the staged diff, the full numbered file (or the enclosing function or class for files over 400 lines), the intent, and definitions from other project files for names used on changed lines. |
| FR5 | The review is one model call that returns JSON with at most three concerns, each tied to a file and line number. |
| FR6 | Concerns are phrased as questions, not verdicts. |
| FR7 | If there are concerns, the commit is blocked unless the developer dismisses them (`d`), uses `--force` / `RUBBERDUCK_FORCE=1`, or runs `git commit --no-verify`. |
| FR8 | If the model is busy or rate limited, RubberDuck retries and then tries any fallback models before giving up. |
| FR9 | An evaluation mode seeds known bugs into real code and measures recall, precision, and false positives with and without intent and context. |

## Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR1 | A review should take a few seconds at most, so it can run on every commit. |
| NFR2 | The API key is read from the environment or a `.env` file and is never committed. |
| NFR3 | The automated tests run without an API key or network access to Gemini. |
| NFR4 | Works on Windows with Python 3.10 or newer. |

## Acceptance criteria

| ID | Criterion | How it is checked |
|----|-----------|-------------------|
| AC1 | `git commit` with a staged Python file triggers the intent prompt and a review. | Live demo (see `demo-tools/`) |
| AC2 | A clean change that matches the intent passes and the commit goes through. | Live demo, `tests/test_review.py` |
| AC3 | A seeded wrong-key, wrong-variable, or wrong-loop bug is flagged on the exact line. | Evaluation runs in `results/` |
| AC4 | Each concern names a file, a line number, and a question. Never more than three. | `tests/test_llm_parse.py` |
| AC5 | Answering `a` blocks the commit; answering `d` allows it. | Live demo (blocking is also covered by `tests/test_review.py`) |
| AC6 | Large files are reduced to the enclosing function or class. | `tests/test_sourceview.py` |
| AC7 | Definitions from other files are added for names used on changed lines. | `tests/test_context.py` |
| AC8 | A busy model is retried, then a fallback model is used. | `tests/test_llm_retry.py` |
| AC9 | The whole test suite passes in CI without an API key. | GitHub Actions (`.github/workflows/ci.yml`) |

## Out of scope

- Languages other than Python
- An editor plugin or other UI (it is terminal only)
- Bug types other than the three above (security, performance, style)
- Letting the model search the codebase on its own (an agent loop)
