# ADR 0005: Measure with seeded bugs

**Status:** Accepted

## Context

To measure recall and precision you need to know where the real bugs are. Collecting and
labeling real-world bugs of these three types would take longer than the course allows.
The original plan was to use MutPy, but it doesn't have operators for these bug types.

## Decision

Write three small mutation operators in `mutations.py` (variable swap, dictionary key swap,
loop collection swap) and apply them to functions in TinyDB, a real but not very famous
Python project. Each buggy function is paired with its clean original. A flag only counts
if it points at the exact seeded line. The function docstring stands in for the intent.

A second, hand-written benchmark (`evaluation/intent_cases.py`) covers cases where the bug
can only be spotted if you know the intent, because both versions of the code look reasonable.

## Consequences

- We know exactly where each bug is, and runs can be repeated.
- Seeded bugs can be easier to spot than real ones, so results may look better than they would in real use.
- Docstrings are a weaker signal than a developer's own intent statement.
