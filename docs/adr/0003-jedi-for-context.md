# ADR 0003: Use jedi for cross-file context

**Status:** Accepted

## Context

A changed line often uses a function or constant defined in another file. Without that
definition the model has to guess what fields or values exist. Sending the whole codebase
would be slow and noisy.

## Decision

Use `jedi`, the library behind "go to definition" in many Python editors. For each name on
a changed line, jedi finds where it is defined. Definitions inside the repository (but not
in the same file) are added to the prompt, up to 6 snippets of 40 lines each.

## Consequences

- No custom symbol lookup to write or maintain.
- Works well for plain names and imports.
- Can't resolve method calls when the object's type isn't clear from the code. That gap is
  accepted for the proof of concept.
