"""Read a skill folder into declared text and executable files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from rubberduck.textio import without_bom

DOC_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}
SCRIPT_SUFFIXES = {".py": "python", ".sh": "shell", ".bash": "shell", ".js": "javascript", ".mjs": "javascript", ".ts": "typescript"}
CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
_MAX_FILE_BYTES = 200_000
_FENCE = re.compile(r"^```(\w+)?\s*$")


@dataclass(frozen=True)
class SkillFile:
    relpath: str
    text: str
    kind: str  # "doc", "script", or "config"
    language: str = ""


@dataclass(frozen=True)
class InlineCode:
    """A fenced code block inside a doc. Agents often run these directly."""

    doc: str
    start_line: int
    language: str
    text: str


@dataclass
class Skill:
    root: Path
    name: str
    description: str
    docs: list[SkillFile] = field(default_factory=list)
    scripts: list[SkillFile] = field(default_factory=list)
    configs: list[SkillFile] = field(default_factory=list)
    inline_code: list[InlineCode] = field(default_factory=list)

    @property
    def python_scripts(self) -> list[SkillFile]:
        return [item for item in self.scripts if item.language == "python"]

    def file(self, relpath: str) -> SkillFile | None:
        for item in (*self.docs, *self.scripts, *self.configs):
            if item.relpath == relpath:
                return item
        return None


def load_skill(root: Path) -> Skill:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a skill folder: {root}")
    docs: list[SkillFile] = []
    scripts: list[SkillFile] = []
    configs: list[SkillFile] = []
    for path in sorted(_iter_files(root)):
        relpath = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix in DOC_SUFFIXES:
            kind, language = "doc", ""
        elif suffix in SCRIPT_SUFFIXES:
            kind, language = "script", SCRIPT_SUFFIXES[suffix]
        elif suffix in CONFIG_SUFFIXES:
            kind, language = "config", suffix.lstrip(".")
        else:
            continue
        text = _read(path)
        if text is None:
            continue
        item = SkillFile(relpath=relpath, text=text, kind=kind, language=language)
        {"doc": docs, "script": scripts, "config": configs}[kind].append(item)

    docs.sort(key=_doc_order)
    meta = {}
    skill_md = next((doc for doc in docs if doc.relpath.lower() == "skill.md"), None)
    if skill_md is not None:
        meta, _ = split_frontmatter(skill_md.text)
    name = meta.get("name") or root.name
    description = meta.get("description", "")
    # Fenced code in SKILL.md and the README is what an agent is told to run.
    # Other docs are usually reference material with example snippets, so they are left out.
    inline = [block for doc in docs if _doc_order(doc)[0] < 2 for block in inline_blocks(doc)]
    return Skill(root=root, name=name, description=description, docs=docs, scripts=scripts, configs=configs, inline_code=inline)


def split_frontmatter(text: str) -> tuple[dict[str, str], int]:
    """Return simple ``key: value`` pairs from a YAML header and the body's first line number.

    Only flat string fields matter here (name, description), so a full YAML
    parser is not needed. Folded values (``>`` or ``|``) are joined.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 1
    meta: dict[str, str] = {}
    key: str | None = None
    for index in range(1, len(lines)):
        raw = lines[index]
        if raw.strip() == "---":
            return {k: v.strip().strip('"').strip("'") for k, v in meta.items()}, index + 2
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if match and not raw.startswith((" ", "\t")):
            key, value = match.group(1), match.group(2).strip()
            meta[key] = "" if value in {">", "|", ">-", "|-"} else value
        elif key is not None and raw.strip():
            meta[key] = (meta[key] + " " + raw.strip()).strip()
    return {}, 1


def inline_blocks(doc: SkillFile) -> list[InlineCode]:
    blocks: list[InlineCode] = []
    lines = doc.text.splitlines()
    index = 0
    while index < len(lines):
        match = _FENCE.match(lines[index].strip())
        if not match:
            index += 1
            continue
        language = (match.group(1) or "").lower()
        start = index + 2
        body: list[str] = []
        index += 1
        while index < len(lines) and not lines[index].strip().startswith("```"):
            body.append(lines[index])
            index += 1
        index += 1
        if language in {"python", "py", "bash", "sh", "shell", "javascript", "js"} and body:
            blocks.append(InlineCode(doc=doc.relpath, start_line=start, language=language, text="\n".join(body)))
    return blocks


def _doc_order(item: SkillFile) -> tuple[int, str]:
    lowered = item.relpath.lower()
    if lowered == "skill.md":
        return (0, lowered)
    if lowered.startswith("readme"):
        return (1, lowered)
    return (2, lowered)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and not path.is_symlink():
            yield path


def _read(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
        return without_bom(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
