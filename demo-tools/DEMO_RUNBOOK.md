# Demo Runbook

How to run the live demo once setup is done (see [DEMO_INSTRUCTIONS.md](./DEMO_INSTRUCTIONS.md)
for setup). Each demo goes: reset, generate, present, reset.

## Files

| Path | What it is |
|---|---|
| `demo/` | The demo repo. Only holds the generated program. Wiped on every reset. |
| `demo-tools/Reset Demo.cmd` | Wipes `demo/` and sets it up again ([RESET_DEMO.md](./RESET_DEMO.md)). |
| `demo-tools/GENERATE_DEMO_PROMPT.md` | Prompt you paste into a coding AI to make a new demo. |
| `demo-tools/CURRENT_DEMO.md` | Notes for the current demo: file name, intent, answer key. Don't show it until after the review. |
| `demo-tools/past-demos/` | Old demos, one folder each. |

## 1. Reset

Close any terminal that's inside `demo/`, then double-click `demo-tools\Reset Demo.cmd`.

## 2. Make a new demo

Open your coding AI with the whole `Rubber-Duck` folder as the workspace. Copy everything in
[GENERATE_DEMO_PROMPT.md](./GENERATE_DEMO_PROMPT.md) and paste it in. It writes a new program to
`demo/` and the notes to `CURRENT_DEMO.md`.

Quick check without reading the answer key: `demo/` should have one `.py` file, it should run with
`python <file>.py`, and the intent in `CURRENT_DEMO.md` should be one line.

## 3. Present

1. Open a terminal in `demo/`. You can run the program first to show it works.
2. Commit it:

   ```
   git add .
   git commit -m "Add demo program"
   ```

3. When it asks "what should this change do?", paste the intent from `CURRENT_DEMO.md` as one line
   and press Enter.
4. Read out RubberDuck's questions.
5. Type `a` to block the commit. Then show the answer key and compare.

To run the same demo again, just repeat the `git commit`. Give it about a minute between runs so you
don't hit the free-tier limit.

## 4. Reset again

Run Reset Demo when you're done. It saves the demo to `past-demos/` first.

## Problems

- **No RubberDuck output:** make sure you're in `demo/` and the file is staged
  (`git status --short`). If it still doesn't run, reset.
- **No intent question:** use `git commit` in a terminal, not the editor's Commit button.
- **Gemini is busy:** RubberDuck retries and then tries the backup models in `.env`. If it still
  fails, wait a minute and commit again.
- **It misses a bug:** the intent might not mention what the bug breaks. Check the intent against
  the answer key, or reset and make a new demo.
