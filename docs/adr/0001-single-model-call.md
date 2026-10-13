# ADR 0001: One model call per file instead of an agent

**Status:** Accepted

## Context

The review could be done by an agent that decides on its own to open more files and ask
follow-up questions, or by a single request that gets all the inputs up front.

## Decision

Each staged file gets exactly one Gemini request. Everything the model needs (rules, intent,
diff, numbered file, related definitions) is gathered by normal Python code first and put
into that one prompt. The response must match a small JSON schema.

## Consequences

- Every run gets the same inputs, so the evaluation conditions are a fair comparison.
- Simpler to build, test, and debug in a seven-week course.
- Fast and cheap enough to run on every commit.
- The model can't go look for more context if what it was given isn't enough. An agent
  version was left as future work.
