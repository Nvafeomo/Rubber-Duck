"""One model call that compares a skill's claims with its code and static facts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Protocol, TypedDict

from rubberduck.llm import ReviewError
from rubberduck.models import Usage
from rubberduck.skills.behaviors import StaticFacts, analyze_skill, format_facts
from rubberduck.skills.claims import Claim, extract_claims, format_claims
from rubberduck.skills.loader import Skill

TYPES = ("unimplemented_intent", "undeclared_behavior", "divergent_behavior")
RISKS = ("low", "medium", "high")
CONDITIONS = ("full", "no_facts", "single_file")
_TYPE_ALIASES = {
    "unimplemented": "unimplemented_intent", "unimplemented intent": "unimplemented_intent",
    "undeclared": "undeclared_behavior", "undeclared behavior": "undeclared_behavior",
    "divergent": "divergent_behavior", "semantically divergent behavior": "divergent_behavior",
    "semantically_divergent_behavior": "divergent_behavior", "divergent behavior": "divergent_behavior",
}

INSTRUCTIONS = """You audit an agent skill for intent-behavior misalignment: places where what the skill says it does (SKILL.md, README, other docs) and what its code does are not the same.

Report only these three types:
- unimplemented_intent: a declared capability or guarantee that no code implements, or that the code only partly implements.
- undeclared_behavior: the code does something with a real effect that the docs never state or clearly imply, such as sending data over the network, reading environment variables or credentials, changing or deleting files outside the described scope, running processes, executing dynamic code, or setting up persistence.
- divergent_behavior: the code does something related to a claim but in a way that differs in a way a user would care about, such as a different target, format, field, or scope, or deleting what the docs say is kept.

First, group the claims into intent units: one unit per thing the skill says it does, merging claims that describe the same capability across files. For each unit, say whether the code implements it (implemented, partial, or missing) and where.

Then report findings. Rules:
- Behavior the docs clearly imply is not a finding. Writing the output file the docs describe is expected.
- Static facts are hints from a pattern scan. Confirm each one in the code before you use it.
- Some behavior only appears when several functions or files run together. Follow the call chain, and report the composite behavior once, at the line where the effect happens.
- Cite a file and line exactly as shown in the numbered sources. For unimplemented_intent, cite the claim's doc file and line and give its claim id.
- evidence lists every relevant location as "file:line". call_chain lists the functions from the entry point to the effect, if any.
- risk is low, medium, or high, based on harm to the user if they trust the docs.
- If the code matches the docs, return an empty findings list. Do not report style, missing tests, or code quality.
- Return at most {max_findings} findings, most serious first.
"""


class FindingSchema(TypedDict):
    type: str
    claim_id: str
    file: str
    line: int
    evidence: list[str]
    call_chain: list[str]
    risk: str
    explanation: str


class IntentSchema(TypedDict):
    summary: str
    claim_ids: list[str]
    status: str
    implemented_at: list[str]


class AuditSchema(TypedDict):
    intents: list[IntentSchema]
    findings: list[FindingSchema]


class JsonModel(Protocol):
    model: str

    def complete_json(self, prompt: str, schema: object, max_output_tokens: int = 1024) -> tuple[str, Usage]:
        """Return the model's JSON text and usage for one call."""


@dataclass(frozen=True)
class Finding:
    type: str
    file: str
    line: int
    explanation: str
    claim_id: str = ""
    evidence: tuple[str, ...] = ()
    call_chain: tuple[str, ...] = ()
    risk: str = "medium"


@dataclass(frozen=True)
class IntentUnit:
    summary: str
    claim_ids: tuple[str, ...]
    status: str  # implemented, partial, missing
    implemented_at: tuple[str, ...] = ()


@dataclass
class AuditResult:
    skill: str
    condition: str
    findings: list[Finding]
    usage: Usage
    files_in_prompt: int
    prompt_chars: int
    claims: list[Claim] = field(default_factory=list)
    intents: list[IntentUnit] = field(default_factory=list)

    def to_json(self) -> str:
        data = {
            "skill": self.skill,
            "condition": self.condition,
            "intents": [asdict(item) for item in self.intents],
            "findings": [asdict(item) for item in self.findings],
            "usage": asdict(self.usage),
            "files_in_prompt": self.files_in_prompt,
            "prompt_chars": self.prompt_chars,
        }
        return json.dumps(data, indent=2)


@dataclass(frozen=True)
class AuditLimits:
    max_lines_per_file: int = 400
    max_total_lines: int = 1200
    max_other_doc_lines: int = 60
    max_doc_lines: int = 300
    max_findings: int = 8
    max_output_tokens: int = 4096


def build_audit_prompt(skill: Skill, claims: list[Claim], facts: StaticFacts | None, condition: str = "full",
                       limits: AuditLimits = AuditLimits()) -> tuple[str, int]:
    """Assemble the prompt. Returns the prompt and the number of files it includes."""
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown condition {condition!r}; use one of {', '.join(CONDITIONS)}")
    parts = [INSTRUCTIONS.replace("{max_findings}", str(limits.max_findings)).strip(), f"Skill: {skill.name}"]
    parts.append("Declared claims (id, doc location, text):\n" + format_claims(claims))

    docs_text = []
    skipped_docs: list[str] = []
    doc_budget = limits.max_doc_lines
    for doc in skill.docs:
        main_doc = doc.relpath.lower() == "skill.md" or doc.relpath.lower().startswith("readme")
        cap = limits.max_lines_per_file if main_doc else min(limits.max_other_doc_lines, max(doc_budget, 0))
        if cap <= 0:
            skipped_docs.append(doc.relpath)
            continue
        docs_text.append(f"=== {doc.relpath} ===\n{_numbered(doc.text, cap)}")
        if not main_doc:
            doc_budget -= min(cap, len(doc.text.splitlines()))
    if skipped_docs:
        docs_text.append(f"(other docs left out for length: {', '.join(skipped_docs[:30])}"
                         f"{' ...' if len(skipped_docs) > 30 else ''})")
    parts.append("Docs (numbered):\n" + ("\n\n".join(docs_text) or "(no docs)"))

    scripts = _pick_scripts(skill, facts, condition)
    remaining = limits.max_total_lines
    code_text = []
    for script in scripts:
        if remaining <= 0:
            code_text.append(f"=== {script.relpath} === (left out: line budget used up)")
            continue
        cap = min(limits.max_lines_per_file, remaining)
        code_text.append(f"=== {script.relpath} ===\n{_numbered(script.text, cap)}")
        remaining -= min(cap, len(script.text.splitlines()))
    parts.append("Code (numbered):\n" + ("\n\n".join(code_text) or "(no scripts; check the docs' own instructions and inline code)"))

    if condition == "full" and facts is not None:
        parts.append("Static facts:\n" + format_facts(facts))
    parts.append(
        'Return JSON: {"intents": [{"summary": string, "claim_ids": [string], "status": "implemented|partial|missing", '
        '"implemented_at": [string]}], "findings": [{"type": "unimplemented_intent|undeclared_behavior|divergent_behavior", '
        '"claim_id": string, "file": string, "line": integer, "evidence": [string], "call_chain": [string], '
        '"risk": "low|medium|high", "explanation": string}]}'
    )
    files = sum(1 for item in [*docs_text, *code_text] if item.startswith("=== ") and "left out" not in item.splitlines()[0])
    return "\n\n".join(parts), files


def audit_skill(skill: Skill, model: JsonModel | None, condition: str = "full",
                limits: AuditLimits = AuditLimits()) -> tuple[AuditResult | None, str]:
    """Run one audit. With ``model=None`` only the prompt is built (dry run)."""
    claims = extract_claims(skill)
    facts = analyze_skill(skill) if condition != "single_file" else None
    prompt, files = build_audit_prompt(skill, claims, facts, condition, limits)
    if model is None:
        return None, prompt
    text, usage = model.complete_json(prompt, AuditSchema, max_output_tokens=limits.max_output_tokens)
    findings = parse_findings(text, limits.max_findings)
    result = AuditResult(skill=skill.name, condition=condition, findings=findings, usage=usage,
                         files_in_prompt=files, prompt_chars=len(prompt), claims=claims, intents=parse_intents(text))
    return result, prompt


def parse_findings(payload: str, max_findings: int = 8) -> list[Finding]:
    text = payload.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReviewError(f"Model response was not JSON: {exc}") from exc
    items = data.get("findings", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ReviewError("Model response findings field was not a list.")
    findings: list[Finding] = []
    seen: set[tuple[str, str, int]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = normalize_type(str(item.get("type", "")))
        line = _as_int(item.get("line"))
        file = str(item.get("file", "")).strip().replace("\\", "/")
        explanation = str(item.get("explanation", "")).strip()
        if kind is None or line is None or line < 1 or not file:
            continue
        key = (kind, file, line)
        if key in seen:
            continue
        seen.add(key)
        risk = str(item.get("risk", "medium")).strip().lower()
        findings.append(Finding(
            type=kind, file=file, line=line, explanation=explanation,
            claim_id=str(item.get("claim_id", "") or "").strip(),
            evidence=tuple(str(x).strip() for x in item.get("evidence", []) or [] if str(x).strip()),
            call_chain=tuple(str(x).strip() for x in item.get("call_chain", []) or [] if str(x).strip()),
            risk=risk if risk in RISKS else "medium",
        ))
        if len(findings) >= max_findings:
            break
    return findings


def parse_intents(payload: str) -> list[IntentUnit]:
    """The intent units are a by-product used for explanations; a bad one is skipped, never fatal."""
    try:
        data = json.loads(payload.strip().removeprefix("```json").removeprefix("```").removesuffix("```"))
    except json.JSONDecodeError:
        return []
    items = data.get("intents", []) if isinstance(data, dict) else []
    units = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not str(item.get("summary", "")).strip():
            continue
        status = str(item.get("status", "")).strip().lower()
        units.append(IntentUnit(
            summary=str(item["summary"]).strip(),
            claim_ids=tuple(str(x).strip() for x in item.get("claim_ids", []) or []),
            status=status if status in {"implemented", "partial", "missing"} else "implemented",
            implemented_at=tuple(str(x).strip() for x in item.get("implemented_at", []) or []),
        ))
    return units


def normalize_type(value: str) -> str | None:
    key = value.strip().lower().replace("-", "_")
    if key in TYPES:
        return key
    return _TYPE_ALIASES.get(key.replace("_", " "), _TYPE_ALIASES.get(key))


def format_findings(result: AuditResult) -> str:
    lines = []
    if result.intents:
        lines.append(f"{result.skill}: {len(result.intents)} intent unit(s)")
        for unit in result.intents:
            where = f" at {', '.join(unit.implemented_at)}" if unit.implemented_at else ""
            lines.append(f"  [{unit.status}] {unit.summary} ({', '.join(unit.claim_ids)}){where}")
    if not result.findings:
        lines.append(f"{result.skill}: no misalignment found.")
        return "\n".join(lines)
    lines.append(f"{result.skill}: {len(result.findings)} finding(s)")
    for index, item in enumerate(result.findings, start=1):
        claim = f" [{item.claim_id}]" if item.claim_id else ""
        lines.append(f"{index}. {item.type}{claim} ({item.risk}) at {item.file}:{item.line}")
        lines.append(f"   {item.explanation}")
        if item.call_chain:
            lines.append(f"   chain: {' -> '.join(item.call_chain)}")
        if item.evidence:
            lines.append(f"   evidence: {', '.join(item.evidence)}")
    return "\n".join(lines)


def _pick_scripts(skill: Skill, facts: StaticFacts | None, condition: str):
    scripts = list(skill.scripts)
    if condition == "single_file":
        main = _main_script(skill)
        return [main] if main else []
    if facts is not None:
        weight = {}
        for behavior in facts.behaviors:
            weight[behavior.file] = weight.get(behavior.file, 0) + {"high": 3, "medium": 2}.get(behavior.risk, 1)
        scripts.sort(key=lambda item: (-weight.get(item.relpath, 0), item.relpath))
    return scripts


def _main_script(skill: Skill):
    """The script the docs mention first, else the first script."""
    if not skill.scripts:
        return None
    docs = "\n".join(doc.text for doc in skill.docs)
    mentioned = [(docs.find(script.relpath), script) for script in skill.scripts if script.relpath in docs]
    mentioned += [(docs.find(script.relpath.rsplit("/", 1)[-1]), script) for script in skill.scripts
                  if script.relpath not in docs and script.relpath.rsplit("/", 1)[-1] in docs]
    if mentioned:
        return min(mentioned, key=lambda pair: pair[0])[1]
    return skill.scripts[0]


def _numbered(text: str, cap: int, max_chars: int = 16_000) -> str:
    lines = text.splitlines()
    shown, used = [], 0
    for line in lines[:cap]:
        used += len(line) + 8
        if used > max_chars:
            break
        shown.append(line)
    cap = len(shown)
    width = len(str(len(shown))) or 1
    body = "\n".join(f"{index:>{width}} | {line}" for index, line in enumerate(shown, start=1))
    if len(lines) > cap:
        body += f"\n... ({len(lines) - cap} more lines not shown)"
    return body


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None
