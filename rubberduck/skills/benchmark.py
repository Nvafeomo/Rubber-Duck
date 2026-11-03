"""Benchmark layout, labels, and collecting skills from public repos.

Each case is a folder::

    benchmark/cases/<case_id>/skill/        copy of the skill
    benchmark/cases/<case_id>/label.json    what is wrong with it, if anything

label.json fields:

    id, origin ("real" or "seeded"), status ("draft" or "verified"),
    source {repo, path, commit, license}, base_case (seeded only),
    aligned (true when the skill has no misalignment),
    misalignments [{type, file, lines, claim, note, related}],
    intents [{summary, source, implemented_at, expected_result}]   (optional, the main things the skill promises)
    behaviors [{category, location, declared}]                    (optional, the effects the code really has)
    suggestions {claims, behaviors}   (pre-filled hints for labeling, never scored)

Only cases with status "verified" are scored unless --include-drafts is given.
Seeded cases are verified by construction.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rubberduck.skills.behaviors import analyze_skill
from rubberduck.skills.claims import extract_claims
from rubberduck.skills.loader import load_skill

LABEL_FILE = "label.json"
SKILL_DIR = "skill"
_TYPES = ("unimplemented_intent", "undeclared_behavior", "divergent_behavior")


@dataclass(frozen=True)
class Misalignment:
    type: str
    file: str
    lines: tuple[int, ...]
    claim: str = ""
    note: str = ""
    related: tuple[str, ...] = ()  # other "file:line" locations that also count as correct


@dataclass
class Case:
    id: str
    root: Path
    origin: str
    status: str
    aligned: bool
    misalignments: list[Misalignment] = field(default_factory=list)
    variant: str = ""
    base_case: str = ""

    @property
    def skill_path(self) -> Path:
        return self.root / SKILL_DIR


def load_cases(bench: Path, include_drafts: bool = False) -> list[Case]:
    cases: list[Case] = []
    for label_path in sorted((bench / "cases").glob(f"*/{LABEL_FILE}")):
        data = json.loads(label_path.read_text(encoding="utf-8"))
        status = data.get("status", "draft")
        if status != "verified" and not include_drafts:
            continue
        problems = validate_label(data)
        if problems:
            raise ValueError(f"{label_path}: " + "; ".join(problems))
        cases.append(Case(
            id=data["id"], root=label_path.parent, origin=data.get("origin", "real"), status=status,
            aligned=bool(data.get("aligned")), variant=data.get("variant", ""), base_case=data.get("base_case", ""),
            misalignments=[Misalignment(type=m["type"], file=m["file"], lines=tuple(int(x) for x in m["lines"]),
                                        claim=m.get("claim", ""), note=m.get("note", ""),
                                        related=tuple(m.get("related", [])))
                           for m in data.get("misalignments", [])],
        ))
    return cases


def validate_label(data: dict) -> list[str]:
    problems = []
    if not data.get("id"):
        problems.append("missing id")
    items = data.get("misalignments", [])
    if data.get("aligned") is None:
        problems.append('set "aligned" to true or false')
    elif data.get("aligned") and items:
        problems.append("aligned is true but misalignments are listed")
    elif data.get("status") == "verified" and not data.get("aligned") and not items:
        problems.append("aligned is false but no misalignments are listed")
    for index, item in enumerate(items):
        if item.get("type") not in _TYPES:
            problems.append(f"misalignment {index}: type must be one of {', '.join(_TYPES)}")
        if not item.get("file"):
            problems.append(f"misalignment {index}: missing file")
        if not item.get("lines") or not all(isinstance(x, int) and x > 0 for x in item.get("lines", [])):
            problems.append(f"misalignment {index}: lines must be a non-empty list of positive integers")
    return problems


def draft_label(case_id: str, skill_dir: Path, source: dict | None = None) -> dict:
    """A label for a human to finish: aligned is unset and hints are filled in."""
    skill = load_skill(skill_dir)
    facts = analyze_skill(skill)
    return {
        "id": case_id,
        "origin": "real",
        "status": "draft",
        "source": source or {},
        "aligned": None,
        "misalignments": [],
        "intents": [],
        "behaviors": [],
        "labeler_notes": "",
        "suggestions": {
            "claims": [f"{c.file}:{c.line} {c.text}" for c in extract_claims(skill)],
            "behaviors": [f"{b.category} ({b.risk}) {b.file}:{b.line} {b.snippet}" for b in facts.behaviors],
            "composite_flows": [f"{f.source.category} {f.source.file}:{f.source.line} -> {f.sink.category} "
                                f"{f.sink.file}:{f.sink.line}" for f in facts.flows],
        },
    }


def write_case(bench: Path, case_id: str, skill_src: Path, label: dict) -> Path:
    root = bench / "cases" / case_id
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(skill_src, root / SKILL_DIR, ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"))
    (root / LABEL_FILE).write_text(json.dumps(label, indent=2) + "\n", encoding="utf-8")
    return root


def find_skill_dirs(repo_dir: Path, require_scripts: bool = True, python_only: bool = False) -> list[Path]:
    found = []
    for skill_md in sorted(repo_dir.rglob("SKILL.md")):
        if ".git" in skill_md.parts:
            continue
        folder = skill_md.parent
        suffixes = {p.suffix.lower() for p in folder.rglob("*") if p.is_file()}
        if python_only and ".py" not in suffixes:
            continue
        if require_scripts and not suffixes & {".py", ".sh", ".js", ".ts", ".mjs", ".bash"}:
            continue
        found.append(folder)
    return found


def collect(repo: str, bench: Path, cache: Path, python_only: bool = True, limit: int | None = None) -> list[str]:
    """Clone (or reuse) a repo and copy its skills into the benchmark as draft cases."""
    local = Path(repo)
    if local.is_dir():
        repo_dir, url, commit = local, str(local.resolve()), _git(["rev-parse", "HEAD"], local)
    else:
        slug = re.sub(r"[^\w.-]+", "_", repo.removeprefix("https://github.com/").removesuffix(".git"))
        repo_dir = cache / slug
        if not repo_dir.exists():
            cache.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--depth", "1", "--quiet", repo, str(repo_dir)], check=True)
        url, commit = repo, _git(["rev-parse", "HEAD"], repo_dir)
    license_name = _license(repo_dir)
    created = []
    for folder in find_skill_dirs(repo_dir, python_only=python_only)[: limit or None]:
        rel = folder.relative_to(repo_dir).as_posix()
        case_id = _case_id(repo_dir.name, rel)
        source = {"repo": url, "path": rel, "commit": commit, "license": license_name}
        if (bench / "cases" / case_id / LABEL_FILE).exists():
            continue  # never overwrite a label someone may have edited
        write_case(bench, case_id, folder, draft_label(case_id, folder, source))
        created.append(case_id)
    return created


def _case_id(repo_name: str, rel: str) -> str:
    tail = rel.strip("/").replace("/", "__") or "root"
    return re.sub(r"[^\w.-]+", "_", f"{repo_name}__{tail}").lower()


def _git(args: list[str], cwd: Path) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _license(repo_dir: Path) -> str:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        path = repo_dir / name
        if path.is_file():
            head = path.read_text(encoding="utf-8", errors="ignore")[:400]
            for marker in ("MIT", "Apache", "BSD", "GPL", "MPL", "ISC", "Unlicense", "CC"):
                if marker.lower() in head.lower():
                    return marker
            return "see LICENSE"
    return "unknown"
