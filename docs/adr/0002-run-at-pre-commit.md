# ADR 0002: Run as a Git pre-commit hook

**Status:** Accepted

## Context

AI review tools usually run on pull requests or when the developer asks for a review.
By then the developer may have moved on and forgotten what each change was meant to do.

## Decision

RubberDuck runs from a Git pre-commit hook. It reviews only staged Python files and asks
for the intent right then, while the change is still fresh.

## Consequences

- No extra step to remember; the review happens on every `git commit`.
- The developer can still dismiss concerns or skip the hook with `--no-verify`.
- The intent prompt needs a real terminal, so committing from an editor's Commit button
  skips the question.
- Each commit waits for one model call, so speed matters (see ADR 0001).
