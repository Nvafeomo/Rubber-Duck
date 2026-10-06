from __future__ import annotations

import subprocess
from pathlib import Path

from rubberduck.models import StagedFile
from rubberduck.textio import without_bom

_GIT = ("git", "-c", "core.quotepath=false")


class GitError(RuntimeError):
    pass


def repo_root(start: Path) -> Path:
    completed = _run(["rev-parse", "--show-toplevel"], start)
    return Path(completed.stdout.strip())


def load_staged_python(repo: Path) -> list[StagedFile]:
    """Return staged Python files with their index diff, index contents, and new-file lines."""
    completed = _run(
        ["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
        repo,
    )
    names = [
        name
        for name in completed.stdout.split("\0")
        if name.endswith(".py")
    ]
    staged: list[StagedFile] = []
    for name in names:
        diff = _run(["diff", "--cached", "--unified=3", "--", name], repo).stdout.replace("\ufeff", "")
        show = _run(["show", f":{name}"], repo, check=False)
        if show.returncode != 0:
            continue
        source = without_bom(show.stdout)
        staged.append(
            StagedFile(
                path=name.replace("\\", "/"),
                diff=diff,
                source=source,
                changed_lines=changed_lines(diff),
            )
        )
    return staged


def changed_lines(diff: str) -> set[int]:
    """Line numbers in the new file that a unified diff adds or replaces.

    Headers such as ``@@ -1,4 +1,5 @@`` set the new-file cursor. A ``+`` line
    (other than the ``+++`` file marker) is a changed line. Deletions do not
    advance the cursor. ``\\ No newline`` markers are ignored.
    """
    lines: set[int] = set()
    new_line: int | None = None
    for line in diff.splitlines():
        if line.startswith("@@"):
            new_line = _hunk_new_start(line)
            continue
        if new_line is None:
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.add(new_line)
            new_line += 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            continue
        new_line += 1
    return lines


def _hunk_new_start(header: str) -> int | None:
    # @@ -l,s +l,s @@ optional section heading
    plus = header.find("+")
    if plus < 0:
        return None
    number = []
    for char in header[plus + 1 :]:
        if char.isdigit():
            number.append(char)
        else:
            break
    if not number:
        return None
    return int("".join(number))


def _run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            [*_GIT, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not on PATH.") from exc
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitError(detail or f"git {' '.join(args)} failed")
    return completed
