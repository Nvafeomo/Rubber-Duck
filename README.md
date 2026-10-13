# RubberDuck

A pre-commit hook that checks your Python code against what you meant it to do.

AI-Assisted Software Engineering (SWENG 889), Penn State Great Valley
Team: Nvafeomo (solo project)

## What it does

When you run `git commit`, RubberDuck asks "what should this change do?" and then sends your
staged code, your answer, and related code from other files to Gemini. If a line doesn't match
what you said, it asks you about that line before the commit goes through.

It looks for three kinds of bugs that run fine but do the wrong thing:

- using the **wrong variable**
- reading the **wrong dictionary key**
- **looping over the wrong list**

The name comes from rubber duck debugging, where you explain your code out loud and catch your
own mistake. This duck can read the code and ask you a question back.

## How it works

1. `git commit` runs the hook, which runs `rubberduck review`.
2. It reads your staged `.py` files (the diff and the full file).
3. It asks for your intent in the terminal.
4. It uses `jedi` to find definitions from other files for names on the changed lines.
5. It sends all of that to Gemini in one request.
6. It prints up to three questions with line numbers, or lets the commit through. You can
   **[a]bort** to fix the code or **[d]ismiss** and commit anyway.

More detail is in [docs/architecture.md](docs/architecture.md),
[docs/requirements.md](docs/requirements.md), and [docs/adr/](docs/adr/).

## Repo layout

```
rubberduck/          the tool
tests/               tests (no API key needed)
evaluation/          intent benchmark (12 cases) and its runner
results/             evaluation results
docs/                requirements, architecture, ADRs
demo-tools/          scripts and guides for the live demo
.github/workflows/   CI (lint, tests, Docker build)
```

## Requirements

- Python 3.10 or newer
- Git
- A Gemini API key (the free tier works): https://aistudio.google.com/apikey
- Docker (optional)

The demo scripts are written for Windows. The tool itself also works on macOS and Linux.

## Setup

```
git clone https://github.com/Nvafeomo/Rubber-Duck.git
cd Rubber-Duck
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

Then add your key. Either copy `.env.example` to `.env` and paste it in, or set it as an
environment variable:

```
setx GEMINI_API_KEY "your-key"          # Windows, then open a new terminal
export GEMINI_API_KEY="your-key"        # macOS/Linux
```

If PowerShell won't run the activate script, you can skip activating and use
`.venv\Scripts\python.exe -m ...` instead.

## Settings

| Variable | Needed? | What it does |
|----------|---------|--------------|
| `GEMINI_API_KEY` | Yes | Your Gemini key (`GOOGLE_API_KEY` also works) |
| `RUBBERDUCK_MODEL` | No | Model to use (default `gemini-3.5-flash-lite`) |
| `RUBBERDUCK_FALLBACK_MODELS` | No | Backup models to try if the main one is busy, comma separated |
| `RUBBERDUCK_INTENT` | No | Use this as the intent instead of asking |
| `RUBBERDUCK_FORCE` | No | Set to `1` to show questions but still allow the commit |

These can also go in a `.env` file at the root of the repo being reviewed.

## Running it

### The demo folder (Windows)

1. Double-click `demo-tools\Reset Demo.cmd`. It makes an empty `demo/` repo with the hook set up.
2. Put a Python file in `demo/`. For the presentation, an AI agent wrote one with three planted
   bugs using `demo-tools/GENERATE_DEMO_PROMPT.md`.
3. In a terminal in `demo/`, run `git add .` and `git commit -m "Add program"`.
4. Type your intent when it asks.

The full demo steps are in [demo-tools/DEMO_RUNBOOK.md](demo-tools/DEMO_RUNBOOK.md), and setup on
a new computer is in [demo-tools/DEMO_INSTRUCTIONS.md](demo-tools/DEMO_INSTRUCTIONS.md). Old demo
programs and their answer keys are in `demo-tools/past-demos/`. The one in the report is
`2026-10-13_0010_payroll`.

### Any other repo

Add a file called `.git/hooks/pre-commit` to that repo:

```
#!/bin/sh
exec rubberduck review
```

`rubberduck` needs to be on your PATH, so activate the virtual environment first. If you use the
[pre-commit](https://pre-commit.com/) framework, `.pre-commit-config.yaml` does the same thing.

You can also run it by hand on staged files:

```
rubberduck review                  # asks for the intent
rubberduck review --intent "..."   # give the intent up front
rubberduck review --dry-run        # show the prompt without calling Gemini
```

Commit from a terminal, not your editor's Commit button, so you can answer the intent question.

## Tests

```
pytest -q
ruff check rubberduck evaluation tests
```

The tests use fake model responses, so they don't need a key. GitHub Actions runs the same
checks on every push and also builds the Docker image. To run the tests in Docker instead:

```
docker compose run --rm tests
```

## Reproducing the evaluation

Both evaluations call Gemini, so you need your key. They pause between calls because of the
free-tier rate limit.

**TinyDB (seeded bugs).** Puts 5 bugs of each type into TinyDB functions and reviews each one,
plus the clean version, four ways: with intent and context, context only, intent only, and
neither. A flag only counts if it's on the exact bugged line. The function's docstring is used
as the intent.

```
rubberduck fetch-corpus
rubberduck eval --repo corpus/tinydb --max-per-class 5 --pause 4 --yes
```

Results go to `results/tinydb-eval.csv`.

**Intent benchmark.** 12 small programs in `evaluation/intent_cases.py` where you can only tell the
code is wrong if you know the intent. Each one is reviewed buggy and clean, with and without the
intent.

```
python -m evaluation.run_intent_eval --pause 4
```

Results go to `results/intent-eval-results.csv`.

With Docker (reads your key from `.env`): `docker compose run --rm tinydb-eval` or
`docker compose run --rm intent-eval`.

## Results

**TinyDB:** 15 bugs and the same 15 functions unchanged. These are the numbers from the class
presentation (see `results/README.md`).

| Condition | Caught | Precision | False alarms | Avg time |
|-----------|--------|-----------|--------------|----------|
| Intent + context | 14/15 | 0.88 | 2/15 | 0.92 s |
| Context only | 14/15 | 0.93 | 1/15 | 0.93 s |
| Intent only | 14/15 | 0.93 | 1/15 | 0.99 s |
| Code only | 14/15 | 0.88 | 2/15 | 0.88 s |

Every version caught 14 of 15, so intent didn't make a difference on these bugs.

**Intent benchmark:** 12 buggy and 12 clean programs.

| Condition | Caught | Precision | False alarms | Avg time |
|-----------|--------|-----------|--------------|----------|
| With intent | 12/12 | 0.92 | 1/12 | 0.96 s |
| Code only | 5/12 | 0.42 | 4/12 | 0.77 s |

Here the intent made a big difference. It matters most when the buggy code looks normal on its own.

## Limitations

- Python only, terminal only.
- Only the three bug types above, so it's not a general code reviewer.
- The questions are only as good as the intent you type.
- `jedi` can't always find where a method is defined if the object's type isn't clear.
- 15 seeded bugs is a small sample, and seeded bugs may be easier than real ones.
- The free tier of Gemini is sometimes busy. RubberDuck retries and tries backup models, but a
  review can still fail. `--pass-on-error` lets the commit through when that happens.

## Credits

- [Google Gemini API](https://ai.google.dev/gemini-api/docs) for the reviews
- [jedi](https://github.com/davidhalter/jedi) for finding definitions in other files
- [TinyDB](https://github.com/msiemens/tinydb) as the evaluation code (downloaded when you run it, not included)
- [pandas](https://pandas.pydata.org/), [pytest](https://pytest.org/), and [ruff](https://docs.astral.sh/ruff/)
- DeepBugs (Pradel and Sen, OOPSLA 2018), the closest earlier work
- I used AI coding assistants to help with parts of the code, tests, and docs, and reviewed and
  tested all of it myself.
