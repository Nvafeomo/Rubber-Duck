# RubberDuck Live Demo: Instructions

Everything needed to run the RubberDuck demo on any Windows PC, including a
fresh school laptop. On a new machine, follow it top to bottom. If you are an
AI agent helping with this demo, read the whole file, then follow
"For an AI agent helping with the demo".

## What the demo shows

1. The presenter states an intent and asks an AI coding agent to write a small,
   readable Python file.
2. The agent is told to slip in three subtle logic bugs (listed below). The code
   still runs without errors.
3. The presenter runs `git add .` and `git commit`. RubberDuck runs
   automatically as a pre-commit hook, asks "what should this change do?",
   and then asks about the exact lines that don't match the intent.

Takeaway: the intent you gave the agent becomes RubberDuck's check on the
agent's code, at the moment you commit.

## The three bug types RubberDuck looks for

| Bug type | Example |
|---|---|
| **Wrong variable** | Returning or comparing a different variable than the one just computed, e.g. `return students` instead of `return passed` |
| **Wrong dictionary key** | Reading the wrong field, e.g. `record["extra_credit"]` where `record["scores"]` was meant |
| **Loop over the wrong collection** | Iterating the wrong list or dict, e.g. `for name in students` when the loop should go over `averages` |

These are the only bug types RubberDuck is tuned for. Syntax errors, crashes
and style issues are not what this demo shows.

## Folder layout

```
Rubber-Duck/                 project root (the cloned repo)
  .venv/                     Python virtual environment (you create it, step 3)
  .env                       optional: your Gemini key (you create it, step 4; never committed)
  rubberduck/                the tool's source code
  demo-tools/                this folder
    DEMO_INSTRUCTIONS.md     this file
    Reset Demo.cmd           double-click to prepare the demo folder
    reset-demo.ps1           what "Reset Demo.cmd" runs
    pre-commit               the git hook that Reset Demo installs
    exclude                  files the demo repo ignores (like .env)
  demo/                      the live demo repo, created by Reset Demo; empty until the agent writes code
```

`demo/` is not in the GitHub repo. Reset Demo creates it on each machine.

## One-time setup on a new PC (about 10 minutes)

### 1. Install the tools

- **Git for Windows:** https://git-scm.com/download/win (default options are fine).
- **Python 3.10 or newer:** https://www.python.org/downloads/
  On the first installer screen, tick **"Add python.exe to PATH"**. If the
  laptop has no admin rights, choose **"Install for me only"** or the
  per-user option. Admin rights aren't needed.

Check both in a new terminal: `git --version` and `python --version`.

### 2. Clone the repo

```
git clone https://github.com/Nvafeomo/Rubber-Duck.git
cd Rubber-Duck
```

If the repo is private, a browser window opens the first time. Sign in with the
same GitHub account. If git asks for your name and email when you commit later,
run `git config --global user.name "Your Name"` and
`git config --global user.email "you@example.com"`.

### 3. Create the virtual environment and install RubberDuck

From the `Rubber-Duck` folder:

```
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

The venv must be named `.venv` and sit in the project root, because the commit
hook looks for `.venv\Scripts\rubberduck.exe` there.

### 4. Add your Gemini API key

You can reuse the key you already have. Go to
https://aistudio.google.com/apikey, sign in with the same Google account, and
copy your existing key (or click **Create API key** for a new one; the free
tier is enough).

Pick **one** of these:

- **Option A (best for a school or shared laptop):** create a file named
  `.env` in the `Rubber-Duck` folder containing one line:
  ```
  GEMINI_API_KEY=paste-your-key-here
  ```
  `.env` is in `.gitignore`, so it never gets pushed. Reset Demo copies it into
  the demo folder automatically. Delete the file when you're done with the
  laptop.
- **Option B (your own PC):** save it as a user environment variable:
  ```
  setx GEMINI_API_KEY "paste-your-key-here"
  ```
  Close every terminal and VS Code window afterwards so new ones see it.
  To remove it later: `reg delete HKCU\Environment /v GEMINI_API_KEY /f`

Never paste the key into a slide, a commit, or the agent chat.

### 5. Prepare the demo folder

Double-click **`demo-tools\Reset Demo.cmd`**. When it says
**"Demo folder is ready"** and **"API key found"**, you're set.

### 6. Rehearse once

Run through "During the demo" below at least once on this laptop. That's the
only real test that the key, the network, and the hook all work there.

## Before every presentation or rehearsal

Double-click **`demo-tools\Reset Demo.cmd`**. It deletes everything in `demo`,
creates a fresh git repo there, and installs the hook. That gives each run a
clean slate.

## During the demo (about 4 minutes)

1. Open the `demo` folder in your editor, and open a terminal in that folder.
2. Say the intent out loud and paste the agent prompt below. The agent writes
   `gradebook.py` in `demo`.
3. Show the code for a few seconds: it's short and looks fine.
4. In the terminal:
   ```
   git add .
   git commit -m "Add gradebook"
   ```
5. RubberDuck asks: **"what should this change do?"** Type the intent.
6. RubberDuck lists up to three questions, each tied to a line number. Read
   them out. At `[a]bort  [d]ismiss and commit:` press `a`. The commit is
   blocked.
7. Optional finale: fix the lines (or ask the agent to), then run the same
   `git add .` and `git commit` again. With no concerns, the commit goes through.

Run `git commit` from a terminal (cmd, PowerShell, or the VS Code terminal),
not the editor's Commit button. The intent prompt needs a terminal to type in.

## The agent prompt

Intent (say it, and type it again when RubberDuck asks):

> Compute each student's average score and return the names of students who
> passed, meaning an average of 70 or higher.

Prompt to paste into the agent:

> Create `gradebook.py` in this folder. It should have:
> - `average_scores(students)`: `students` is a dict mapping a name to a dict
>   with keys `"scores"` (list of numbers) and `"extra_credit"` (number). Return
>   a dict mapping each name to the average of its scores plus extra credit.
> - `passing_students(students)`: return a list of names whose average is 70 or
>   higher.
> - A small `if __name__ == "__main__":` block with three sample students.
>
> Keep it short and readable. For this demo, deliberately include exactly these
> three subtle bugs, and make sure the file still runs without errors:
> 1. Wrong dictionary key: read `"extra_credit"` where `"scores"` should be used
>    (or the reverse) in one spot.
> 2. Loop over the wrong collection: in `passing_students`, loop over the wrong
>    list or dict.
> 3. Wrong variable: return or compare a different variable than the one just
>    computed.
>
> No comments or names that hint at the bugs, and don't tell me which lines
> they're on.

Any small topic works (shopping cart, inventory, grades). Keep the intent to one
clear sentence and the file short enough to read on screen.

## For an AI agent helping with the demo

If the presenter asks you to help with this demo:

1. **Setup check:** confirm `.venv\Scripts\rubberduck.exe` exists in the
   project root, and that a Gemini key is available (`GEMINI_API_KEY` set, or a
   `.env` file in the project root). If anything is missing, walk the presenter
   through "One-time setup". Never print, echo, or ask to see the key.
2. **Reset:** ask the presenter to double-click `demo-tools\Reset Demo.cmd`,
   or run `powershell -ExecutionPolicy Bypass -File demo-tools\reset-demo.ps1`
   from the project root.
3. **Writing the demo file:** write one short Python file in `demo` that does
   what the presenter's intent says. Include only the bug types the presenter
   asks for, all from the table above. The code must run without errors. No
   comments, names, or messages that hint at the bugs.
4. **Hands off the commit:** don't run `git add` or `git commit` in `demo`.
   The presenter does that live.
5. **Stay in scope:** don't edit or delete anything outside `demo`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Set GEMINI_API_KEY or GOOGLE_API_KEY` | No key visible. Add `.env` (step 4, option A) and run Reset Demo again, or open a new terminal after `setx`. |
| Reset Demo says `Can't find ...rubberduck.exe` | Step 3 wasn't done in this clone. Create `.venv` in the project root and run `pip install -e .`. |
| Commit goes through with no RubberDuck output | The demo wasn't reset (no hook), or no `.py` file was staged. Run Reset Demo, then try again. |
| Intent prompt never appears | You committed from the editor's Commit button. Use `git commit` in a terminal. |
| Reset Demo window flashes and closes, or scripts are blocked | Run it from a terminal instead: `powershell -ExecutionPolicy Bypass -File demo-tools\reset-demo.ps1`. If PowerShell is fully locked down, do it by hand from the project root: `mkdir demo`, `cd demo`, `git init`, `git commit --allow-empty -m "Start demo"`, `copy ..\demo-tools\pre-commit .git\hooks\`, `copy ..\demo-tools\exclude .git\info\`, and `copy ..\.env .` if you use option A. |
| Network or school firewall blocks the API | Use a phone hotspot, or play your backup recording of the demo. |
| Agent saved the file somewhere else | Move it into `demo`, then `git add .` again. |
