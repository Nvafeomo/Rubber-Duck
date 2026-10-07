# Reset the Demo

Run this after every demo, and before generating a new one. It wipes the
`demo/` folder so the next review considers only the new program.

## How to run it

**Option 1: double-click**

1. In File Explorer, open `Rubber-Duck\demo-tools`.
2. Double-click **`Reset Demo.cmd`**.
3. Wait for the green **"Demo folder is ready and empty"** line, then press any
   key to close the window.

**Option 2: terminal**

From the `Rubber-Duck` folder (not `demo`), run:

```powershell
powershell -ExecutionPolicy Bypass -File demo-tools\internals\reset-demo.ps1
```

## Before you run it

- **Close any terminal that is inside `demo/`**, or `cd` out of it. Windows
  can't delete a folder that a terminal is using, so the reset would fail.
- Nothing is lost. The finished demo is moved, not deleted (see below).

## What it does

1. **Archives** the previous program and `demo-tools/CURRENT_DEMO.md` into
   `demo-tools/past-demos/<date>_<program>/`. You'll see an
   "Archived the previous demo…" line.
2. **Deletes everything in `demo/`** and creates a fresh Git repository there
   with one empty commit. No earlier code, history, or staged files remain.
3. **Installs** the RubberDuck pre-commit hook and copies the project-root
   `.env` (your API key) into `demo/`.
4. **Checks** that `demo/` is clean, and stops with an error if it isn't.

## After it finishes

1. Paste [GENERATE_DEMO_PROMPT.md](./GENERATE_DEMO_PROMPT.md) into your
   coding AI to create the next demo.
2. Open a new terminal in `demo/` for the presentation.

## Rerunning without a reset

To show the **same** demo again (for a rehearsal, say), you don't need to
reset. Aborting with `a` leaves the program staged, so you can just run
`git commit -m "Add demo program"` again.

To bring back an **earlier** demo: reset, copy its `.py` file from
`demo-tools/past-demos/<folder>/` into `demo/`, and copy that folder's
`NOTES.md` to `demo-tools/CURRENT_DEMO.md`.
