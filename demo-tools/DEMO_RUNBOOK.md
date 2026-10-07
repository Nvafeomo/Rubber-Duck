# RubberDuck Demo Runbook

Use this guide for the live demo after the one-time setup is complete and the
Gemini key is available. For installation or setup on another machine, see
[DEMO_INSTRUCTIONS.md](./DEMO_INSTRUCTIONS.md).

Every demo follows the same loop: **reset → generate → present → reset**.
Each run gets a new program on a new topic, so no two demos are the same.

## Demo goal

A coding AI writes one readable Python program with three intentional logic
bugs, one of each kind RubberDuck targets:

| Bug kind | Example |
|---|---|
| Wrong dictionary key | `record["homework"]` where `record["exams"]` was meant |
| Wrong collection in a loop | `for name in tutoring:` where every student was meant |
| Wrong variable | `return top_average` where `top_student` was meant |

You commit the program, RubberDuck asks for your intent, and it raises a
line-specific question about each bug. The answer key stays outside the demo
repository, so the review sees only the program.

## Where things live

| Path | What it is |
|---|---|
| `demo/` | The live demo repository. Holds only the generated program. Wiped by every reset. |
| `demo-tools/RESET_DEMO.md` | How to wipe `demo/` after a demo (and what the reset does). |
| `demo-tools/GENERATE_DEMO_PROMPT.md` | The prompt you paste into the coding AI to create a new demo. |
| `demo-tools/CURRENT_DEMO.md` | Presenter notes for the current demo: program name, the one-line intent, and the answer key. Don't show it until after the review. |
| `demo-tools/past-demos/` | One folder per finished demo (program plus notes). Reset fills it, and the coding AI reads it to pick a new topic. |

## 1. Reset

Follow [RESET_DEMO.md](./RESET_DEMO.md). In short: close any terminal inside
`demo/`, double-click `demo-tools\Reset Demo.cmd`, and wait for **"Demo folder
is ready and empty"**. The previous demo is archived to `past-demos/`, and
`demo/` becomes a fresh, empty repository, so the next review considers only
the new program.

## 2. Generate a new demo

Open the coding AI with the **Rubber-Duck project folder** as its workspace, so
it can write to both `demo/` and `demo-tools/`. Then open
[GENERATE_DEMO_PROMPT.md](./GENERATE_DEMO_PROMPT.md), copy all of it
(Ctrl+A, Ctrl+C), and paste it into the coding AI unchanged.

The prompt has the AI pick a topic that isn't in `past-demos/`, write the
program to `demo/<topic>.py` with one bug of each kind, and write the intent and
answer key to `demo-tools/CURRENT_DEMO.md`.

Then check the result without reading the answer key:

- `demo/` contains exactly one `.py` file, and it runs: `python <topic>.py`.
- `demo-tools/CURRENT_DEMO.md` exists and its intent is a single line.

If either check fails, ask the coding AI to fix it, or reset and generate again.

## 3. Present

1. Open a terminal in `demo/`. Optionally run `python <topic>.py` to show that
   the program runs and prints a plausible report.
2. Stage and commit:

   ```powershell
   git add .
   git status --short
   git commit -m "Add demo program"
   ```

   `git status --short` should list one line, `A  <topic>.py`. Because the reset
   started a fresh repository, that file is the only thing RubberDuck reviews.
3. At `RubberDuck: what should this change do?`, paste the **Intent** line
   from `CURRENT_DEMO.md` and press Enter. Paste it as one line; text after a
   newline is run as a separate shell command.
4. RubberDuck lists up to three questions in the form *"Should it be [correct]
   instead of [what the code has]?"*. Read them out.
5. At `[a]bort  [d]ismiss and commit:`, type `a` and press Enter. The commit is
   blocked and the program stays staged. Anything other than `d` also aborts.
6. Open `CURRENT_DEMO.md` and compare the answer key with RubberDuck's
   questions.

Run `git commit` in a terminal, not the editor's Commit button, so the hook can
ask for the intent.

To repeat the same demo (for example, during a rehearsal), run the `git commit`
command again. Aborting leaves everything staged, so no reset is needed. Leave
about a minute between runs to stay under the free-tier rate limit.

## 4. Reset after the demo

Run the reset again ([RESET_DEMO.md](./RESET_DEMO.md)). It also explains how to
bring back an earlier demo from `past-demos/`.

## Troubleshooting

- **No RubberDuck output:** confirm the terminal is in `demo/`, that the
  program is staged (`git status --short`), and that
  `demo/.git/hooks/pre-commit` exists. If not, run Reset Demo.
- **The intent prompt does not appear:** run `git commit` from a terminal
  instead of using the editor's Commit button.
- **Missing API key:** rerun Reset Demo after confirming the key is in the
  project-root `.env`; it copies that file into `demo/`. Never paste the key
  into the coding-agent prompt or the presenter notes.
- **Gemini is busy (503 UNAVAILABLE, 429, or a timeout):** RubberDuck retries
  once (each attempt waits up to 20 seconds), then tries each model in
  `RUBBERDUCK_FALLBACK_MODELS` from `.env` (currently
  `gemini-flash-lite-latest,gemini-3.8-flash`). Retry messages appear in the
  terminal; let them finish. If it still fails, the commit is blocked and
  nothing needs resetting: wait a minute and run `git commit` again.
- **RubberDuck misses a bug or asks about something else:** the seeded bug may
  be too subtle, or the intent may not mention the behavior it breaks. Check the
  intent against the answer key, or reset and generate a new demo.
- **A seeded bug is absent or the program crashes:** reset and generate again.
  The demonstration depends on three observable logic bugs and a successful
  program run.
