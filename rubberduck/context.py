from __future__ import annotations

import ast
from pathlib import Path

from rubberduck.models import Settings, Snippet
from rubberduck.textio import without_bom


def related_snippets(
    source: str,
    file_path: Path,
    changed: set[int],
    repo: Path,
    settings: Settings,
) -> list[Snippet]:
    """Definitions in other project files for names used on changed lines.

    Uses jedi the way an editor's go-to-definition does. Unresolvable attributes
    (a method call on a value whose type cannot be read off the code) are skipped.
    Anything outside the repository, including the standard library, is skipped.
    """
    try:
        import jedi
    except ImportError:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    targets = _lookup_targets(tree, changed)
    if not targets:
        return []

    project = jedi.Project(str(repo))
    try:
        script = jedi.Script(code=source, path=str(file_path), project=project)
    except Exception:
        return []

    snippets: list[Snippet] = []
    seen: set[tuple[str, int]] = set()
    repo_resolved = repo.resolve()
    origin = file_path.resolve()
    for line, column in targets:
        try:
            definitions = script.goto(line, column, follow_imports=True)
        except Exception:
            continue
        for definition in definitions:
            module_path = getattr(definition, "module_path", None)
            def_line = getattr(definition, "line", None)
            if module_path is None or def_line is None:
                continue
            resolved = Path(module_path).resolve()
            if resolved == origin:
                continue
            try:
                relpath = resolved.relative_to(repo_resolved).as_posix()
            except ValueError:
                continue
            key = (relpath, int(def_line))
            if key in seen:
                continue
            numbered = _definition_text(resolved, int(def_line), settings.max_snippet_lines)
            if not numbered:
                continue
            seen.add(key)
            description = getattr(definition, "description", "") or getattr(definition, "name", "")
            snippets.append(
                Snippet(
                    relpath=relpath,
                    line=int(def_line),
                    description=str(description),
                    numbered=numbered,
                )
            )
            if len(snippets) >= settings.max_snippets:
                return snippets
    return snippets


def format_snippets(snippets: list[Snippet]) -> str:
    blocks = [
        f"# {snippet.relpath}:{snippet.line} {snippet.description}\n{snippet.numbered}"
        for snippet in snippets
    ]
    return "\n\n".join(blocks)


def _lookup_targets(tree: ast.AST, changed: set[int]) -> list[tuple[int, int]]:
    targets: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.lineno in changed:
            targets.append((node.lineno, node.col_offset))
        elif isinstance(node, ast.Attribute) and node.lineno in changed and node.end_col_offset:
            column = node.end_col_offset - len(node.attr)
            if column >= 0:
                targets.append((node.lineno, column))
    return targets


def _definition_text(path: Path, line: int, max_lines: int) -> str:
    try:
        source = without_bom(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return ""
    file_lines = source.splitlines()
    if not file_lines or line < 1 or line > len(file_lines):
        return ""
    start, end = _enclosing_span(source, line)
    if end - start + 1 > max_lines:
        end = start + max_lines - 1
    return "\n".join(
        f"{number}| {file_lines[number - 1]}"
        for number in range(start, min(end, len(file_lines)) + 1)
    )


def _enclosing_span(source: str, line: int) -> tuple[int, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return line, line
    best: tuple[int, int] | None = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.end_lineno is None:
            continue
        if node.lineno <= line <= node.end_lineno:
            span = (node.lineno, node.end_lineno)
            if best is None or (span[1] - span[0]) < (best[1] - best[0]):
                best = span
    if best is None:
        return line, line
    return best
