from __future__ import annotations

import ast
import random
from pathlib import Path

from rubberduck.context import format_snippets, related_snippets
from rubberduck.llm import Reviewer
from rubberduck.metrics import condition_inputs, score_flags
from rubberduck.models import EvalRow, SeededBug, Settings, Usage
from rubberduck.mutations import OPERATORS, apply_operator
from rubberduck.prompt import build_prompt, focus_label
from rubberduck.sourceview import line_change_block, select_view
from rubberduck.textio import without_bom

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".tox",
    "site-packages",
    "docs",
}
_TEST_DIRS = {"tests", "test", "testing"}


def discover_bugs(
    repo: Path,
    *,
    max_per_class: int,
    seed: int,
    include_tests: bool,
) -> list[SeededBug]:
    """Seed at most ``max_per_class`` bugs of each operator from functions in ``repo``."""
    found: list[SeededBug] = []
    for path in _python_files(repo, include_tests=include_tests):
        try:
            source = without_bom(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
        if source.count("\n") > 5000:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        relpath = path.relative_to(repo).as_posix()
        file_lines = source.splitlines(keepends=True)
        for node, qualname in _iter_functions(tree):
            if node.end_lineno is None or node.end_lineno - node.lineno < 1:
                continue
            start = node.lineno
            if node.decorator_list:
                start = min(start, min(item.lineno for item in node.decorator_list))
            segment = "".join(file_lines[start - 1 : node.end_lineno])
            docstring = ast.get_docstring(node)
            for operator in OPERATORS:
                mutation = apply_operator(segment, operator)
                if mutation is None:
                    continue
                mutated_file = _splice(source, start, node.end_lineno, mutation.source)
                found.append(
                    SeededBug(
                        relpath=relpath,
                        path=str(path),
                        qualname=qualname,
                        docstring=docstring,
                        operator=operator,
                        absolute_line=start + mutation.line - 1,
                        file_source=source,
                        mutated_source=mutated_file,
                        description=mutation.description,
                    )
                )
    return _sample(found, max_per_class=max_per_class, seed=seed)


def review_bug(
    bug: SeededBug,
    *,
    kind: str,
    condition: str,
    repo: Path,
    client: Reviewer,
    settings: Settings,
) -> EvalRow:
    include_intent, include_context = condition_inputs(condition)
    start, end = _function_bounds(bug)
    source = bug.mutated_source if kind == "bug" else bug.file_source
    if kind == "bug":
        diff = line_change_block(_function_slice(bug), _mutated_slice(bug), start)
        changed = {bug.absolute_line}
        focus = focus_label(changed)
        if not diff:
            diff = bug.description
    else:
        diff = f"Function {bug.qualname} is under review (lines {start}-{end})."
        changed = set(range(start, end + 1))
        focus = f"{start}-{end}"
    numbered = select_view(source, changed, settings.max_file_lines, settings.max_scope_lines)
    context = None
    if include_context:
        snippets = related_snippets(source, Path(bug.path), changed, repo, settings)
        context = format_snippets(snippets) or None
    intent = None
    if include_intent:
        intent = (bug.docstring or f"{bug.qualname} should keep its current behavior.").strip()
    prompt = build_prompt(
        relpath=bug.relpath,
        diff=diff,
        numbered_source=numbered,
        focus=focus,
        intent=intent,
        context=context,
    )
    completion = client.complete(prompt)
    return _row(bug, kind, condition, completion.concerns, completion.usage, settings.model)


def unique_functions(bugs: list[SeededBug]) -> list[SeededBug]:
    """One clean review per function, even when several operators seeded it."""
    seen: set[tuple[str, str]] = set()
    chosen: list[SeededBug] = []
    for bug in bugs:
        key = (bug.relpath, bug.qualname)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(bug)
    return chosen


def iter_jobs(bugs: list[SeededBug], conditions: list[str], include_clean: bool):
    cleans = unique_functions(bugs) if include_clean else []
    for condition in conditions:
        for bug in bugs:
            yield condition, "bug", bug
        for bug in cleans:
            yield condition, "clean", bug


def planned_calls(bugs: list[SeededBug], conditions: list[str], include_clean: bool) -> int:
    return sum(1 for _ in iter_jobs(bugs, conditions, include_clean))


def _row(bug, kind, condition, concerns, usage: Usage, model: str) -> EvalRow:
    bug_line = bug.absolute_line if kind == "bug" else None
    hit, flagged, n_flags, n_correct, flag_lines, questions = score_flags(
        concerns,
        kind=kind,
        bug_line=bug_line,
        relpath=bug.relpath,
    )
    return EvalRow(
        condition=condition,
        kind=kind,
        operator="" if kind == "clean" else bug.operator,
        file=bug.relpath,
        function=bug.qualname,
        bug_line=bug_line,
        hit=hit,
        flagged=flagged,
        n_flags=n_flags,
        n_correct_flags=n_correct,
        flag_lines=flag_lines,
        questions=questions,
        latency_s=usage.latency_s,
        prompt_tokens=usage.prompt_tokens,
        output_tokens=usage.output_tokens,
        model=model,
    )


def _sample(found: list[SeededBug], *, max_per_class: int, seed: int) -> list[SeededBug]:
    rng = random.Random(seed)
    selected: list[SeededBug] = []
    for operator in OPERATORS:
        group = [bug for bug in found if bug.operator == operator]
        documented = [bug for bug in group if bug.docstring]
        undocumented = [bug for bug in group if not bug.docstring]
        rng.shuffle(documented)
        rng.shuffle(undocumented)
        selected.extend((documented + undocumented)[:max_per_class])
    return selected


def _python_files(repo: Path, *, include_tests: bool):
    skip = set(_SKIP_DIRS)
    if not include_tests:
        skip |= _TEST_DIRS
    for path in sorted(repo.rglob("*.py")):
        if any(part in skip for part in path.parts):
            continue
        yield path


def _iter_functions(tree: ast.AST):
    def visit(node: ast.AST, prefix: list[str]):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield from visit(child, prefix + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield child, ".".join([*prefix, child.name])
                yield from visit(child, prefix + [child.name])

    yield from visit(tree, [])


def _splice(source: str, start: int, end: int, segment: str) -> str:
    lines = source.splitlines(keepends=True)
    replacement = segment.splitlines(keepends=True)
    if replacement and not replacement[-1].endswith(("\n", "\r")) and end <= len(lines):
        replacement[-1] = replacement[-1] + "\n"
    return "".join([*lines[: start - 1], *replacement, *lines[end:]])


def _function_bounds(bug: SeededBug) -> tuple[int, int]:
    """Locate the seeded function again from its original line.

    The absolute bug line sits inside the function, and the function's first
    line is ``absolute_line - mutation.line + 1``. Re-parse to recover the end.
    """
    tree = ast.parse(bug.file_source)
    for node, qualname in _iter_functions(tree):
        if qualname != bug.qualname or node.end_lineno is None:
            continue
        start = node.lineno
        if node.decorator_list:
            start = min(start, min(item.lineno for item in node.decorator_list))
        if start <= bug.absolute_line <= node.end_lineno:
            return start, node.end_lineno
    raise ValueError(f"Could not relocate {bug.qualname} in {bug.relpath}")


def _function_slice(bug: SeededBug) -> str:
    start, end = _function_bounds(bug)
    lines = bug.file_source.splitlines()
    return "\n".join(lines[start - 1 : end]) + "\n"


def _mutated_slice(bug: SeededBug) -> str:
    start, end = _function_bounds(bug)
    lines = bug.mutated_source.splitlines()
    return "\n".join(lines[start - 1 : end]) + "\n"

