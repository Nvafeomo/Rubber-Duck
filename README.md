# RubberDuck

**Intent-aware detection of subtle logic bugs at commit time**

AI-Assisted Software Engineering (SWENG 889), Penn State Great Valley
Team: Nvafeomo (solo project)

## What it is

RubberDuck is a Git pre-commit hook for Python. When you run `git commit`, it asks
"what should this change do?", then sends the staged code, your answer, and related
definitions from other files to Gemini in a single request. If a line doesn't match what
you said you meant, it asks you about that line before the commit goes through.

It targets three kinds of bugs that run without errors but do the wrong thing:

- using the **wrong variable**
- reading the **wrong dictionary key**
- **looping over the wrong collection**

The name comes from rubber duck debugging: explaining your code out loud to catch your own
mistakes. RubberDuck replaces the silent duck with one that can read the code and ask back.

## How it works

1. `git commit` runs the pre-commit hook, which runs `rubberduck review`.
2. RubberDuck reads the staged `.py` files: the diff, the full staged file, and which lines changed.
3. It asks for your intent in the terminal.
4. It uses `jedi` to find definitions from other files for names on the changed lines.
5. One Gemini call gets the rules, intent, diff, numbered file, and related definitions.
6. It prints up to three questions tied to line numbers, or passes. You can **[a]bort** the
   commit to fix things or **[d]ismiss** and commit anyway.

More detail: [docs/architecture.md](docs/architecture.md),
[docs/requirements.md](docs/requirements.md), and the decision records in [docs/adr/](docs/adr/).

## Repository layout

```
rubberduck/          the tool (CLI, git diff reading, context, prompt, Gemini client, evaluation)
tests/               pytest suite (no API key needed)
evaluation/          12-case intent benchmark and its runner
results/             evaluation output (CSV)
docs/                requirements, architecture, ADRs
demo-tools/          scripts and runbook for the live demo
.github/workflows/   CI: lint, tests, Docker build
Dockerfile, docker-compose.yml   container setup for tests and evaluations
```

## Requirements

- Windows, macOS, or Linux (the demo scripts are for Windows)
- Python 3.10 or newer
- Git
- A Google Gemini API key (free tier works): https://aistudio.google.com/apikey
- Optional: Docker, to run tests or evaluations in a container

## Setup

```
git clone https://github.com/Nvafeomo/Rubber-Duck.git
cd Rubber-Duck
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

Then add your API key. Either copy `.env.example` to `.env` and paste the key there
(`.env` is gitignored), or set it as an environment variable:

```
setx GEMINI_API_KEY "your-key"          # Windows (open a new terminal afterwards)
export GEMINI_API_KEY="your-key"        # macOS/Linux
```

## Configuration

| Variable | Required | What it does |
|----------|----------|--------------|
| `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | Yes | Access to the Gemini API |
| `RUBBERDUCK_MODEL` | No | Model to use. Default: `gemini-3.5-flash-lite` |
| `RUBBERDUCK_FALLBACK_MODELS` | No | Comma-separated models to try if the main one is busy |
| `RUBBERDUCK_INTENT` | No | Skip the intent prompt and use this text |
| `RUBBERDUCK_FORCE` | No | Set to `1` to print concerns but allow the commit |

RubberDuck also reads a `.env` file in the root of the repository being reviewed.

## Running the proof of concept

### Option 1: the demo folder (Windows)

1. Double-click `demo-tools\Reset Demo.cmd`. It creates an empty `demo/` Git repo with the
   hook installed.
2. Put a Python file in `demo/` (for the presentation, an AI agent wrote one with three
   planted bugs, see `demo-tools/GENERATE_DEMO_PROMPT.md`).
3. In a terminal in `demo/`:
   ```
   git add .
   git commit -m "Add program"
   ```
4. Type the intent when asked, then read the questions.

Full steps, including setup on a new machine: [demo-tools/DEMO_INSTRUCTIONS.md](demo-tools/DEMO_INSTRUCTIONS.md).
Two earlier demo programs and their notes are in `demo-tools/past-demos/`.

### Option 2: any repository

Create `.git/hooks/pre-commit` in that repo with:

```
#!/bin/sh
exec rubberduck review
```

(`rubberduck` must be on the PATH, for example by activating the virtual environment first.)
You can also run it by hand on staged files:

```
rubberduck review                      # asks for the intent
rubberduck review --intent "..."       # intent given up front
rubberduck review --dry-run            # print the prompt, no model call
```

Commit from a terminal, not an editor's Commit button, so the intent prompt can be answered.

## Running the tests

```
pytest -q
ruff check rubberduck evaluation tests
```

The tests use fake model responses and temporary Git repos, so they need no API key.
The same checks run in GitHub Actions on every push (`.github/workflows/ci.yml`), along with
a Docker build that runs the tests inside the container.

With Docker:

```
docker compose run --rm tests
```

## Reproducing the evaluation

Both evaluations call Gemini, so they need the API key. The free tier has rate limits, so
the scripts pause between calls (`--pause`).

### 1. Seeded bugs in TinyDB (four conditions)

Seeds 5 bugs of each type into functions from TinyDB, reviews each buggy function and its
clean original under four conditions (full, context-only, intent-only, code-only), and
scores a hit only when the flag points at the exact seeded line. The function docstring is
used as the intent.

```
rubberduck fetch-corpus
rubberduck seed --repo corpus/tinydb --max-per-class 5            # list the bugs, no API calls
rubberduck eval --repo corpus/tinydb --max-per-class 5 --pause 4 --yes
```

Output: `results/tinydb-eval.csv` plus a summary table printed at the end.

### 2. Intent benchmark (12 hand-written cases)

`evaluation/intent_cases.py` has 12 small programs where the bug only shows up if you know
what the code was supposed to do. Each case is reviewed buggy and clean, with and without
the intent.

```
python -m evaluation.run_intent_eval --pause 4
```

Output: `results/intent-eval-results.csv`.

With Docker (key read from `.env`):

```
docker compose run --rm tinydb-eval
docker compose run --rm intent-eval
```

## Results

TinyDB seeded-bug evaluation (15 bugs, 5 per type, plus the same 15 functions left clean),
as presented in class:

| Condition | Recall | Precision | False alarms on clean code | Avg latency |
|-----------|--------|-----------|----------------------------|-------------|
| Full (intent + context) | 14/15 (0.93) | 0.88 | 2/15 | 0.92 s |
| Context only | 14/15 (0.93) | 0.93 | 1/15 | 0.93 s |
| Intent only | 14/15 (0.93) | 0.93 | 1/15 | 0.99 s |
| Code only (baseline) | 14/15 (0.93) | 0.88 | 2/15 | 0.88 s |

Every condition caught 14 of 15 bugs, so on these bugs intent and context made no
measurable difference. The one miss was the same dictionary key swap each time.

Intent benchmark (12 hand-written cases where the bug only shows up if you know the intent,
each reviewed buggy and clean):

| Condition | Recall | Precision | False alarms on clean code | Avg latency |
|-----------|--------|-----------|----------------------------|-------------|
| With intent | 12/12 | 0.92 | 1/12 | 0.96 s |
| Code only | 5/12 | 0.42 | 4/12 | 0.77 s |

With the intent, every bug type was caught 4 of 4 times. Without it, wrong dictionary keys and
wrong variables were caught 2 of 4 times and wrong loop collections 1 of 4. Intent matters most
for bugs where the code looks reasonable on its own. Raw rows are in `results/intent-eval-results.csv`.

## Known limitations

- Python only, terminal only.
- Only the three bug types above. It is not a general code reviewer.
- Questions are only as good as the intent you type.
- `jedi` can't always resolve method calls on objects whose type isn't obvious.
- Seeded bugs may be easier to spot than real ones, and 15 bugs is a small sample.
- Free-tier Gemini can be busy or rate limited. RubberDuck retries and can switch to fallback
  models, but a review can still fail (use `--pass-on-error` to let the commit through then).
- Committing from an editor's Commit button skips the intent prompt.

## External resources and acknowledgments

- [Google Gemini API](https://ai.google.dev/gemini-api/docs): the model behind each review
- [jedi](https://github.com/davidhalter/jedi): cross-file "go to definition"
- [TinyDB](https://github.com/msiemens/tinydb): evaluation corpus (cloned at run time, not included)
- [pandas](https://pandas.pydata.org/), [pytest](https://pytest.org/), [ruff](https://docs.astral.sh/ruff/)
- M. Pradel and K. Sen, "DeepBugs: A Learning Approach to Name-based Bug Detection," OOPSLA 2018: closest prior work
- AI coding assistants were used to help write parts of the code, tests, and documentation.
  All of it was reviewed, run, and tested by the author.
