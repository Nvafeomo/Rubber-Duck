"""Score audit findings against benchmark labels and run the comparison."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from rubberduck.llm import ReviewError
from rubberduck.skills.audit import CONDITIONS, AuditResult, Finding, audit_skill
from rubberduck.skills.baselines import BASELINES, run_baseline
from rubberduck.skills.benchmark import Case, Misalignment
from rubberduck.skills.claims import extract_claims
from rubberduck.skills.loader import load_skill

METHODS = (*CONDITIONS, *BASELINES)
_TYPES = ("unimplemented_intent", "undeclared_behavior", "divergent_behavior")
_SHORT = {"unimplemented_intent": "unimpl", "undeclared_behavior": "undecl", "divergent_behavior": "diverg"}


@dataclass(frozen=True)
class Score:
    n_labels: int
    n_findings: int
    correct_findings: int
    matched_labels: int
    located_findings: int
    labels_by_type: dict[str, int]
    hits_by_type: dict[str, int]


def score(case: Case, findings: list[Finding], claim_lines: dict[str, tuple[str, int]], tolerance: int = 3) -> Score:
    """Greedy one-to-one matching. A finding is correct when its type matches a
    label and it points within ``tolerance`` lines of that label (by its own
    location, any evidence location, or the claim it cites)."""
    labels = list(case.misalignments)
    used: set[int] = set()
    correct = located = 0
    hits = {kind: 0 for kind in _TYPES}
    for finding in findings:
        spots = _finding_spots(finding, claim_lines)
        match = None
        for index, label in enumerate(labels):
            if index in used or label.type != finding.type:
                continue
            if _near(spots, _label_spots(label), tolerance):
                match = index
                break
        if match is not None:
            used.add(match)
            correct += 1
            hits[labels[match].type] += 1
        if any(_near(spots, _label_spots(label), tolerance) for label in labels):
            located += 1
    by_type = {kind: sum(1 for label in labels if label.type == kind) for kind in _TYPES}
    return Score(n_labels=len(labels), n_findings=len(findings), correct_findings=correct, matched_labels=len(used),
                 located_findings=located, labels_by_type=by_type, hits_by_type=hits)


def run(cases: list[Case], methods: list[str], model, out_dir: Path, pause_s: float = 0.0,
        tolerance: int = 3, progress=print) -> pd.DataFrame:
    rows = []
    findings_dir = out_dir / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    total = len(cases) * len(methods)
    done = 0
    for case in cases:
        skill = load_skill(case.skill_path)
        claim_lines = {claim.id: (claim.file, claim.line) for claim in extract_claims(skill)}
        for method in methods:
            done += 1
            error = ""
            result: AuditResult | None = None
            try:
                if method in BASELINES:
                    result = run_baseline(method, skill)
                else:
                    if model is None:
                        raise ReviewError("no model configured")
                    result, _ = audit_skill(skill, model, condition=method)
                    if pause_s:
                        time.sleep(pause_s)
            except ReviewError as exc:
                error = str(exc)[:300]
            findings = result.findings if result else []
            sc = score(case, findings, claim_lines, tolerance)
            if result is not None:
                (findings_dir / f"{case.id}__{method}.json").write_text(result.to_json() + "\n", encoding="utf-8")
            row = {
                "case": case.id, "origin": case.origin, "variant": case.variant or ("aligned" if case.aligned else "real"),
                "aligned": case.aligned, "method": method,
                "n_labels": sc.n_labels, "n_findings": sc.n_findings, "correct_findings": sc.correct_findings,
                "matched_labels": sc.matched_labels, "located_findings": sc.located_findings,
                "latency_s": round(result.usage.latency_s, 3) if result else None,
                "prompt_tokens": result.usage.prompt_tokens if result else None,
                "output_tokens": result.usage.output_tokens if result else None,
                "files_in_prompt": result.files_in_prompt if result else None,
                "model": getattr(model, "model", "") if method not in BASELINES else "",
                "error": error,
            }
            for kind in _TYPES:
                row[f"labels_{_SHORT[kind]}"] = sc.labels_by_type[kind]
                row[f"hits_{_SHORT[kind]}"] = sc.hits_by_type[kind]
            rows.append(row)
            status = f"error: {error[:60]}" if error else f"{sc.correct_findings}/{sc.n_findings} correct, {sc.matched_labels}/{sc.n_labels} found"
            progress(f"[{done}/{total}] {case.id} {method}: {status}")
    return pd.DataFrame(rows)


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    out = []
    for method, group in frame.groupby("method", sort=False):
        ok = group[group["error"] == ""]
        findings = ok["n_findings"].sum()
        labels = ok["n_labels"].sum()
        aligned = ok[ok["aligned"]]
        row = {
            "method": method,
            "cases": len(ok),
            "errors": int((group["error"] != "").sum()),
            "precision": _ratio(ok["correct_findings"].sum(), findings),
            "recall": _ratio(ok["matched_labels"].sum(), labels),
            "false_alarm_rate": _ratio((aligned["n_findings"] > 0).sum(), len(aligned)),
        }
        p, r = row["precision"], row["recall"]
        row["f1"] = round(2 * p * r / (p + r), 3) if p and r else None
        for kind in _SHORT.values():
            row[f"recall_{kind}"] = _ratio(ok[f"hits_{kind}"].sum(), ok[f"labels_{kind}"].sum())
        row["avg_latency_s"] = round(ok["latency_s"].mean(), 3) if len(ok) else None
        row["avg_prompt_tokens"] = round(ok["prompt_tokens"].dropna().mean(), 1) if ok["prompt_tokens"].notna().any() else None
        out.append(row)
    return pd.DataFrame(out)


def summarize_by_variant(frame: pd.DataFrame) -> pd.DataFrame:
    ok = frame[frame["error"] == ""]
    grouped = ok.groupby(["variant", "method"], sort=False).agg(
        cases=("case", "count"), labels=("n_labels", "sum"), found=("matched_labels", "sum"),
        findings=("n_findings", "sum"), correct=("correct_findings", "sum"))
    grouped["recall"] = (grouped["found"] / grouped["labels"].where(grouped["labels"] > 0)).round(3)
    return grouped.reset_index()


def _finding_spots(finding: Finding, claim_lines: dict[str, tuple[str, int]]) -> list[tuple[str, int]]:
    spots = [(finding.file, finding.line)]
    for item in finding.evidence:
        parsed = _parse_spot(item)
        if parsed:
            spots.append(parsed)
    if finding.claim_id in claim_lines:
        spots.append(claim_lines[finding.claim_id])
    return spots


def _label_spots(label: Misalignment) -> list[tuple[str, int]]:
    spots = [(label.file, line) for line in label.lines]
    for item in label.related:
        parsed = _parse_spot(item)
        if parsed:
            spots.append(parsed)
    return spots


def _parse_spot(text: str) -> tuple[str, int] | None:
    file, sep, rest = text.strip().rpartition(":")
    digits = "".join(ch for ch in rest.split("-")[0] if ch.isdigit())
    if not sep or not file or not digits:
        return None
    return file.strip(), int(digits)


def _near(a: list[tuple[str, int]], b: list[tuple[str, int]], tolerance: int) -> bool:
    return any(_same_file(fa, fb) and abs(la - lb) <= tolerance for fa, la in a for fb, lb in b)


def _same_file(a: str, b: str) -> bool:
    a, b = a.replace("\\", "/").strip("./"), b.replace("\\", "/").strip("./")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def _ratio(num, den) -> float | None:
    return round(float(num) / float(den), 3) if den else None


def write_summary(frame: pd.DataFrame, out_dir: Path, name: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / f"{name}.csv"
    frame.to_csv(rows_path, index=False)
    summary_path = out_dir / f"{name}-summary.csv"
    summarize(frame).to_csv(summary_path, index=False)
    summarize_by_variant(frame).to_csv(out_dir / f"{name}-by-variant.csv", index=False)
    return rows_path, summary_path

