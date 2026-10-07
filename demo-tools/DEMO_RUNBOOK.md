# RubberDuck Demo Runbook

Use this guide for the live demo after the one-time setup is complete and the
Gemini key is available. For installation or setup on another machine, see
[DEMO_INSTRUCTIONS.md](./DEMO_INSTRUCTIONS.md).

## Demo goal

Ask a coding AI to create one substantial, readable Python program with three
intentional logic bugs. Keep the bug answer key out of the demo repository.
Stage and commit only the program, then show RubberDuck asking for your intent
and raising questions about the staged code.

## Before the demo

1. From the Rubber-Duck project folder, run `demo-tools\Reset Demo.cmd`.
   This recreates `demo/`, initializes its Git repository, installs the hook,
   and copies the root `.env` into `demo/`. **It deletes everything currently
   inside `demo/`**, so save anything you need first.
2. Open `demo/` in your editor and open a terminal whose current directory is
   `demo/`.
3. Use the intent and coding-agent prompt below. The coding agent should write
   the program in `demo/gradebook.py`. Put the answer key and any other
   presenter-only demo materials in `demo-tools/`, not in `demo/`, so they are
   easy to find and cannot be staged with the demo code. The answer key is for
   the presenter; do not open or show it until after RubberDuck has run.

## Intent to tell the coding AI

Paste this as one line when RubberDuck asks for the intent (the prompt reads one
line; pressing Enter submits it):

```text
Calculate each student's course average using 40% homework and 60% exam scores, then list every student whose average is at least 70%.
```

Give the coding AI the same intent. Do not paste a multi-line paragraph into
the terminal prompt; text after the first newline is treated as a new shell
command.

## Prompt for the coding AI

Paste this while the coding AI is working in the Rubber-Duck project. Ensure
the project folder is its workspace, so it can create the answer key under
`demo-tools/` as well as the program under `demo/`.

> Create a single, decent-sized but readable Python program at `demo/gradebook.py`
> for a small course gradebook. Aim for roughly 80–120 lines. It should run
> directly with `python gradebook.py`, include realistic sample data for at
> least six students, and print a useful report. Organize it into a few
> straightforward functions: calculate each student's average from homework
> and exam scores, determine who passed a configurable threshold, summarize
> course results, and print the report. Use only the Python standard library.
>
> Deliberately seed exactly three subtle logic bugs, one of each kind:
> 1. **Wrong dictionary key:** use a valid but incorrect score field (for
>    example, use homework scores where exam scores are intended). Both fields
>    must exist and have compatible values, so the program still runs.
> 2. **Wrong collection in a loop:** iterate over a different, valid collection
>    than the function's purpose requires. Make the supplied data demonstrate
>    the resulting omission or incorrect inclusion, without raising an error.
> 3. **Wrong variable:** use a different in-scope variable than the value just
>    computed in one calculation or return. Make this produce a plausible but
>    incorrect result, without raising an error.
>
> Make each bug observable in the printed results, but keep the code syntactically
> valid and free of runtime errors. Do not add comments, names, or output that
> identify the bugs. Do not reveal the bugs in your response.
>
> Also create `demo-tools/GRADEBOOK_ANSWER_KEY.md` for the presenter. In that
> file only, describe the three seeded bugs, identify their functions and
> relevant expressions (not guessed line numbers), explain the correct logic
> and the visible effect in the sample output. Do not put the answer key in
> `demo/`. Save any other presenter-only demo notes or materials under
> `demo-tools/` as well. Do not print the answer key in chat, and do not stage
> or commit anything.

## Live demo

1. Look over `demo/gradebook.py` without opening the answer key. Optionally run
   `python gradebook.py` to show that it executes and prints a plausible report.
2. In the terminal in `demo/`, stage and commit the program:

   ```powershell
   git add gradebook.py
   git status --short
   git commit -m "Add gradebook report"
   ```

   Confirm that `git status --short` lists only `gradebook.py` before
   committing. Do not run `git add .` from the Rubber-Duck project root. The
   answer key is outside the demo repository and must not be staged.
3. At `RubberDuck: what should this change do?`, paste the intent above and
   press Enter.
4. Read RubberDuck's line-specific questions. At `[a]bort [d]dismiss and
   commit:`, enter `a` to demonstrate that the commit is blocked.
5. After the review, find `GRADEBOOK_ANSWER_KEY.md` in `demo-tools/` and
   compare its notes with the reported concerns. Keep the answer key and any
   other presenter-only demo materials in `demo-tools/`; they are not part of
   the demo commit.

Run `git commit` in the terminal, not the editor's Commit button, so the hook
can prompt for input. If there are no staged `.py` changes, the hook has
nothing to review.

## Reset between runs

Run `demo-tools\Reset Demo.cmd` again to get a clean demo repository. This
clears `demo/`, but leaves `demo-tools/GRADEBOOK_ANSWER_KEY.md` intact. Remove
or update that answer key yourself if you want to preserve a record or generate
a new one.

## Troubleshooting

- **No RubberDuck output:** confirm the terminal is in `demo/`, that
  `gradebook.py` is staged, and that `demo/.git/hooks/pre-commit` exists.
- **The intent prompt does not appear:** run `git commit` from a terminal
  instead of using the editor's Commit button.
- **Missing API key:** rerun Reset Demo after confirming the key is in the
  project-root `.env`; it copies that file into `demo/`. Never paste the key
  into the coding-agent prompt or the answer key.
- **A seeded bug is absent or the program crashes:** fix or regenerate the
  program before staging it. The demonstration depends on exactly three
  observable logic bugs and a successful program run.
