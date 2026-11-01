"""Non-LLM baselines the challenge asks to compare against.

* ``rules``: static analysis plus keyword checks. A medium or high risk behavior
  whose category is never mentioned in the docs is undeclared; a claim whose
  content words never show up in the code is unimplemented.
* ``similarity``: lexical similarity (TF-IDF cosine). A claim with no similar
  function is unimplemented; a risky behavior with no similar doc text is
  undeclared.

Neither can find divergent behavior, which needs reading what the code means.
That gap is part of what the evaluation shows.
"""

from __future__ import annotations

import ast
import math
import re
import time
from collections import Counter

from rubberduck.models import Usage
from rubberduck.skills.audit import AuditResult, Finding
from rubberduck.skills.behaviors import analyze_skill
from rubberduck.skills.claims import extract_claims
from rubberduck.skills.loader import Skill

BASELINES = ("rules", "similarity")
_STOP = set("""a an the and or of to in on for with by from as at is are be this that it its into your you use used
when what which will can may should must not no all any each every if then than so also only more most such via using
file files skill skills user users run runs script scripts code""".split())
_CATEGORY_WORDS = {
    "network": ("http", "api", "upload", "send", "request", "url", "download", "network", "server", "webhook",
                "fetch", "online", "internet", "endpoint", "post", "remote", "web"),
    "env_read": ("environment variable", "env var", "api key", "token", "credential", "secret", ".env", "environ"),
    "credential_access": ("credential", "ssh", "keychain", "password", "secret", "token"),
    "process": ("command", "shell", "subprocess", "execute", "cli", "terminal", "invoke", "run "),
    "dynamic_code": ("eval", "plugin", "execute code", "dynamic", "exec"),
    "file_delete": ("delete", "remove", "clean", "clear", "purge"),
    "persistence": ("cron", "startup", "schedule", "bashrc", "profile", "background"),
    "clipboard": ("clipboard", "paste", "copy"),
}
_MIN_RISK = {"medium", "high"}


def run_baseline(name: str, skill: Skill) -> AuditResult:
    started = time.perf_counter()
    if name == "rules":
        findings = _rules(skill)
    elif name == "similarity":
        findings = _similarity(skill)
    else:
        raise ValueError(f"Unknown baseline {name!r}")
    usage = Usage(latency_s=time.perf_counter() - started, prompt_tokens=0, output_tokens=0)
    return AuditResult(skill=skill.name, condition=name, findings=findings, usage=usage,
                       files_in_prompt=len(skill.docs) + len(skill.scripts), prompt_chars=0)


def _rules(skill: Skill) -> list[Finding]:
    docs = "\n".join(doc.text for doc in skill.docs).lower()
    facts = analyze_skill(skill)
    findings: list[Finding] = []
    for behavior in facts.behaviors:
        if behavior.risk not in _MIN_RISK:
            continue
        words = _CATEGORY_WORDS.get(behavior.category, ())
        if words and not any(word in docs for word in words):
            findings.append(Finding(type="undeclared_behavior", file=behavior.file, line=behavior.line, risk=behavior.risk,
                                    explanation=f"{behavior.category} ({behavior.api}) is not mentioned in the docs"))
    code_tokens = _code_tokens(skill)
    for claim in extract_claims(skill):
        words = [w for w in _words(claim.text) if len(w) > 3]
        if len(words) >= 3 and not any(_stem(w) in code_tokens for w in words):
            findings.append(Finding(type="unimplemented_intent", file=claim.file, line=claim.line, claim_id=claim.id,
                                    explanation="no word from this claim appears in the code"))
    return findings


def _similarity(skill: Skill, claim_threshold: float = 0.08, behavior_threshold: float = 0.05) -> list[Finding]:
    units = _function_units(skill)
    claims = extract_claims(skill)
    doc_units = [claim.text for claim in claims] or [doc.text for doc in skill.docs]
    corpus = [_bag(text) for text in [*units.values(), *doc_units]]
    idf = _idf(corpus)
    unit_vecs = [_tfidf(_bag(text), idf) for text in units.values()]
    findings: list[Finding] = []
    if unit_vecs:
        for claim in claims:
            vec = _tfidf(_bag(claim.text), idf)
            if not vec:
                continue
            best = max(_cosine(vec, other) for other in unit_vecs)
            if best < claim_threshold:
                findings.append(Finding(type="unimplemented_intent", file=claim.file, line=claim.line, claim_id=claim.id,
                                        explanation=f"no function resembles this claim (best similarity {best:.2f})"))
    doc_vecs = [_tfidf(_bag(text), idf) for text in doc_units]
    for behavior in analyze_skill(skill).behaviors:
        if behavior.risk not in _MIN_RISK:
            continue
        text = f"{behavior.category.replace('_', ' ')} {behavior.api} {behavior.snippet}"
        vec = _tfidf(_bag(text), idf)
        best = max((_cosine(vec, other) for other in doc_vecs), default=0.0)
        if best < behavior_threshold:
            findings.append(Finding(type="undeclared_behavior", file=behavior.file, line=behavior.line, risk=behavior.risk,
                                    explanation=f"{behavior.category} has no similar text in the docs (best {best:.2f})"))
    return findings


def _function_units(skill: Skill) -> dict[str, str]:
    units: dict[str, str] = {}
    for script in skill.scripts:
        if script.language != "python":
            units[script.relpath] = script.text
            continue
        try:
            tree = ast.parse(script.text)
        except SyntaxError:
            units[script.relpath] = script.text
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                units[f"{script.relpath}::{node.name}"] = ast.get_source_segment(script.text, node) or node.name
        units.setdefault(script.relpath, script.text)
    return units


def _code_tokens(skill: Skill) -> set[str]:
    text = "\n".join(script.text for script in skill.scripts)
    text += "\n".join(block.text for block in skill.inline_code)
    return {_stem(word) for word in _words(text)}


def _words(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [w for w in re.findall(r"[a-z][a-z0-9]+", text.lower().replace("_", " ")) if w not in _STOP]


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _bag(text: str) -> Counter:
    return Counter(_stem(w) for w in _words(text))


def _idf(corpus: list[Counter]) -> dict[str, float]:
    n = len(corpus) or 1
    df = Counter(term for bag in corpus for term in bag)
    return {term: math.log((1 + n) / (1 + count)) + 1 for term, count in df.items()}


def _tfidf(bag: Counter, idf: dict[str, float]) -> dict[str, float]:
    return {term: count * idf.get(term, 1.0) for term, count in bag.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(term, 0.0) for term, value in a.items())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0
