from __future__ import annotations

import ast


def select_view(
    source: str,
    changed: set[int],
    max_file_lines: int,
    max_scope_lines: int,
) -> str:
    """Numbered source for the model.

    Files within ``max_file_lines`` are sent whole. Larger files are reduced
    to the tightest function or class around each changed line, and a single
    scope is windowed to ``max_scope_lines`` so one long function cannot
    dominate the request. Line numbers stay the original file numbers.
    """
    lines = source.splitlines()
    if not lines:
        return ""
    if len(lines) <= max_file_lines or not changed:
        if len(lines) <= max_file_lines:
            return _render(lines, [(1, len(lines))])
        focus = sorted(changed) or [1]
        mid = focus[len(focus) // 2]
        start, end = _window(1, len(lines), mid, max_file_lines)
        return _render(lines, [(start, end)])

    spans = _spans_for_changes(source, changed, max_scope_lines)
    if not spans:
        focus = sorted(changed)
        mid = focus[len(focus) // 2]
        start, end = _window(1, len(lines), mid, max_scope_lines)
        spans = [(start, end)]
    return _render(lines, spans)


def line_change_block(original: str, mutated: str, start: int) -> str:
    """Show only the lines a mutation changed, with absolute file numbers."""
    old_lines = original.splitlines()
    new_lines = mutated.splitlines()
    blocks: list[str] = []
    shared = min(len(old_lines), len(new_lines))
    for offset in range(shared):
        if old_lines[offset] == new_lines[offset]:
            continue
        number = start + offset
        blocks.append(
            f"Line {number}:\n- {old_lines[offset]}\n+ {new_lines[offset]}"
        )
    if len(old_lines) != len(new_lines):
        blocks.append(
            f"(length changed from {len(old_lines)} to {len(new_lines)} lines "
            f"starting at line {start})"
        )
    return "\n".join(blocks)


def _spans_for_changes(
    source: str,
    changed: set[int],
    max_scope_lines: int,
) -> list[tuple[int, int]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    scopes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.end_lineno
    ]
    chosen: list[tuple[int, int]] = []
    for line in sorted(changed):
        covering = [
            node
            for node in scopes
            if node.lineno <= line <= (node.end_lineno or node.lineno)
        ]
        if not covering:
            start, end = _window(1, len(source.splitlines()), line, 30)
            chosen.append((start, end))
            continue
        tight = min(
            covering,
            key=lambda node: (
                (node.end_lineno or node.lineno) - node.lineno,
                0 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else 1,
            ),
        )
        start = tight.lineno
        decorators = getattr(tight, "decorator_list", None) or []
        if decorators:
            start = min(start, min(node.lineno for node in decorators))
        end = tight.end_lineno or tight.lineno
        start, end = _window(start, end, line, max_scope_lines)
        chosen.append((start, end))
    return _merge(chosen)


def _window(start: int, end: int, focus: int, cap: int) -> tuple[int, int]:
    if end - start + 1 <= cap:
        return start, end
    half = cap // 2
    window_start = max(start, focus - half)
    window_end = min(end, window_start + cap - 1)
    window_start = max(start, window_end - cap + 1)
    return window_start, window_end


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end + 1:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def _render(lines: list[str], spans: list[tuple[int, int]]) -> str:
    chunks: list[str] = []
    for index, (start, end) in enumerate(spans):
        if index:
            chunks.append("... omitted ...")
        for number in range(start, end + 1):
            if 1 <= number <= len(lines):
                chunks.append(f"{number}| {lines[number - 1]}")
    return "\n".join(chunks)
