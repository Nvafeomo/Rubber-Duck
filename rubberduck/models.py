from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Limits that keep a pre-commit review small enough to run on every commit."""

    max_file_lines: int = 400
    max_scope_lines: int = 200
    max_snippets: int = 6
    max_snippet_lines: int = 40
    model: str = "gemini-3.8-flash"


@dataclass(frozen=True)
class Concern:
    file: str
    line: int
    question: str


@dataclass(frozen=True)
class Usage:
    latency_s: float
    prompt_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class Completion:
    concerns: list[Concern]
    usage: Usage


@dataclass(frozen=True)
class StagedFile:
    path: str
    diff: str
    source: str
    changed_lines: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class Snippet:
    relpath: str
    line: int
    description: str
    numbered: str


@dataclass(frozen=True)
class Mutation:
    operator: str
    source: str
    line: int
    description: str


@dataclass(frozen=True)
class SeededBug:
    relpath: str
    path: str
    qualname: str
    docstring: str | None
    operator: str
    absolute_line: int
    file_source: str
    mutated_source: str
    description: str


@dataclass(frozen=True)
class EvalRow:
    condition: str
    kind: str
    operator: str
    file: str
    function: str
    bug_line: int | None
    hit: bool
    flagged: bool
    n_flags: int
    n_correct_flags: int
    flag_lines: str
    questions: str
    latency_s: float
    prompt_tokens: int | None
    output_tokens: int | None
    model: str
