# ADR 0004: Ask questions instead of declaring bugs

**Status:** Accepted

## Context

The model only sees part of the codebase and a one-line intent. It will sometimes be wrong,
and a tool that confidently reports false bugs on every commit gets turned off.

## Decision

The prompt tells the model to phrase each concern as a short question about one line, to
return at most three, and to return nothing when the change fits the intent. Style, type
hints, missing tests, and design opinions are explicitly off limits.

## Consequences

- Output stays short and easy to act on ("Line 5: should this use worked_hours?").
- The developer stays in charge and can dismiss a question that doesn't apply.
- Some real issues outside the three bug types will not be mentioned.
