"""Split a skill's declarative files into short, numbered claims.

Claims are kept as quoted text with a file and line, so every finding can point
back to the exact sentence that made the promise. Splitting is rule-based on
purpose: it is cheap, repeatable, and the model still sees the full docs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rubberduck.skills.loader import Skill, SkillFile, split_frontmatter

_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`\"'(])")
_MIN_WORDS = 4
_MAX_CLAIMS = 40


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    file: str
    line: int
    section: str = ""


def extract_claims(skill: Skill, max_claims: int = _MAX_CLAIMS) -> list[Claim]:
    raw: list[tuple[str, str, int, str]] = []
    if skill.description:
        skill_md = next((doc for doc in skill.docs if doc.relpath.lower() == "skill.md"), None)
        line = _description_line(skill_md) if skill_md else 1
        for sentence in _sentences(skill.description):
            raw.append((sentence, skill_md.relpath if skill_md else "SKILL.md", line, "description"))
    for doc in skill.docs:
        raw.extend(_doc_claims(doc))

    claims: list[Claim] = []
    seen: set[str] = set()
    for text, file, line, section in raw:
        key = _normalize(text)
        if key in seen or len(key.split()) < _MIN_WORDS:
            continue
        seen.add(key)
        claims.append(Claim(id=f"C{len(claims) + 1}", text=text, file=file, line=line, section=section))
        if len(claims) >= max_claims:
            break
    return claims


def format_claims(claims: list[Claim]) -> str:
    if not claims:
        return "(no declared claims found)"
    return "\n".join(f"[{claim.id}] {claim.file}:{claim.line} {claim.text}" for claim in claims)


def _doc_claims(doc: SkillFile) -> list[tuple[str, str, int, str]]:
    out: list[tuple[str, str, int, str]] = []
    _, body_start = split_frontmatter(doc.text) if doc.relpath.lower() == "skill.md" else ({}, 1)
    lines = doc.text.splitlines()
    section = ""
    in_fence = False
    paragraph: list[str] = []
    paragraph_line = 0

    def flush() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph)
            for sentence in _sentences(text):
                out.append((sentence, doc.relpath, paragraph_line, section))
            paragraph = []

    for number, raw in enumerate(lines, start=1):
        if number < body_start:
            continue
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = _HEADING.match(raw)
        if heading:
            flush()
            section = _clean(heading.group(1))
            continue
        if not stripped or stripped.startswith(("|", ">", "<!--")):
            flush()
            continue
        bullet = _BULLET.match(raw)
        if bullet:
            flush()
            text = _clean(bullet.group(1))
            if text:
                out.append((text, doc.relpath, number, section))
            continue
        if not paragraph:
            paragraph_line = number
        paragraph.append(_clean(raw))
    flush()
    return out


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return [part.strip() for part in _SENTENCE_END.split(text) if part.strip()]


def _clean(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # markdown links -> label
    text = text.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", text).strip()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _description_line(doc: SkillFile) -> int:
    for number, raw in enumerate(doc.text.splitlines(), start=1):
        if raw.lstrip().startswith("description:"):
            return number
    return 1
