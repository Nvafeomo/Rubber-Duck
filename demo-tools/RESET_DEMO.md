# Resetting the Demo

Do this after every demo and before making a new one.

## How

Close any terminal that's inside `demo/` first, since Windows can't delete a folder that's open.
Then either:

- double-click `demo-tools\Reset Demo.cmd`, or
- run this from the `Rubber-Duck` folder:
  `powershell -ExecutionPolicy Bypass -File demo-tools\internals\reset-demo.ps1`

## What it does

1. Saves the last demo program and `CURRENT_DEMO.md` to `demo-tools/past-demos/`.
2. Deletes everything in `demo/` and starts a new empty Git repo there.
3. Installs the RubberDuck hook and copies your `.env` into `demo/`.

Nothing gets lost, since the old demo is moved to `past-demos/` first.

## Bringing back an old demo

Reset, copy the `.py` file from its `past-demos/` folder into `demo/`, and copy that folder's
`NOTES.md` to `demo-tools/CURRENT_DEMO.md`.
