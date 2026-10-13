# Demo Setup on a New Computer

Follow this once on any Windows computer you want to run the demo on. After that, use
[DEMO_RUNBOOK.md](./DEMO_RUNBOOK.md) for the actual demo.

## What the demo shows

An AI agent writes a short Python program with three planted bugs. You commit it, RubberDuck
asks what the code should do, and then it asks about each bugged line.

| Bug type | Example |
|---|---|
| Wrong variable | `return students` instead of `return passed` |
| Wrong dictionary key | `record["extra_credit"]` instead of `record["scores"]` |
| Wrong list in a loop | `for name in students` instead of `for name in averages` |

## Setup (about 10 minutes)

**1. Install Git and Python 3.10+.**
Git: https://git-scm.com/download/win. Python: https://www.python.org/downloads/ (check
"Add python.exe to PATH"; "Install for me only" works without admin rights).

**2. Clone the repo.**

```
git clone https://github.com/Nvafeomo/Rubber-Duck.git
cd Rubber-Duck
```

If git asks for your name and email when you commit, set them with
`git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`.

**3. Install RubberDuck.**

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

The folder has to be called `.venv` and be in the project root, because the demo hook looks for
it there.

**4. Add your Gemini key.**
Get it from https://aistudio.google.com/apikey (same Google account works on every computer).
On a school or shared laptop, make a file called `.env` in the `Rubber-Duck` folder with one line:

```
GEMINI_API_KEY=your-key
```

`.env` is gitignored, so it won't get pushed. Delete it when you're done with that laptop.
On your own computer you can use `setx GEMINI_API_KEY "your-key"` instead, then reopen your
terminals.

**5. Set up the demo folder.**
Double-click `demo-tools\Reset Demo.cmd` and wait for the "ready" message.

**6. Do one practice run** with the [runbook](./DEMO_RUNBOOK.md) to make sure the key and network
work on this computer.

## If you're an AI agent helping with the demo

- Check that `.venv\Scripts\rubberduck.exe` exists and a key is set (env variable or `.env`).
  Never print or ask for the key.
- To reset, ask the presenter to double-click `demo-tools\Reset Demo.cmd`.
- To make a new demo, follow [GENERATE_DEMO_PROMPT.md](./GENERATE_DEMO_PROMPT.md).
- Don't run `git add` or `git commit` in `demo/`. The presenter does that live.
- Only change files in `demo/` and `demo-tools/CURRENT_DEMO.md`.

## Problems

| Problem | Fix |
|---|---|
| "Set GEMINI_API_KEY or GOOGLE_API_KEY" | Add the `.env` file and run Reset Demo again, or open a new terminal after `setx`. |
| Reset Demo can't find `rubberduck.exe` | Step 3 wasn't done in this copy of the repo. |
| Commit goes through with no RubberDuck output | Run Reset Demo again, and make sure a `.py` file is staged. |
| No intent question | You used the editor's Commit button. Use `git commit` in a terminal. |
| Reset Demo window closes right away | Run `powershell -ExecutionPolicy Bypass -File demo-tools\internals\reset-demo.ps1` from the project folder. |
| School network blocks the API | Use a phone hotspot or a recording of the demo. |
