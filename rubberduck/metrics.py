from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from rubberduck.models import Concern, EvalRow

CONDITIONS = ("full", "context-only", "intent-only", "code-only")


def condition_inputs(name: str) -> tuple[bool, bool]:
    """Return ``(include_intent, include_context)`` for an evaluation condition."""
    table = {
        "full": (True, True),
        "context-only": (False, True),
        "intent-only": (True, False),
        "code-only": (False, False),
    }
    if name not in table:
        known = ", ".join(CONDITIONS)
        raise ValueError(f"Unknown condition {name!r}. Expected one of: {known}")
    return table[name]


def file_matches(concern_file: str, relpath: str) -> bool:
    if not concern_file:
        return True
    concern = concern_file.replace("\\", "/").lstrip("./")
    target = relpath.replace("\\", "/")
    if concern == target or target.endswith("/" + concern) or concern.endswith("/" + target):
        return True
    return Path(concern).name == Path(target).name


def score_flags(
    concerns: list[Concern],
    *,
    kind: str,
    bug_line: int | None,
    relpath: str,
) -> tuple[bool, bool, int, int, str, str]:
    """A hit is a concern on the exact mutated line in that file.

    Precision later counts every concern: ones on the mutated line are correct,
    and every concern on untouched code is not.
    """
    n_flags = len(concerns)
    if kind == "bug" and bug_line is not None:
        n_correct = sum(
            1
            for concern in concerns
            if concern.line == bug_line and file_matches(concern.file, relpath)
        )
        hit = n_correct > 0
    else:
        n_correct = 0
        hit = False
    flag_lines = ";".join(str(concern.line) for concern in concerns)
    questions = " | ".join(concern.question for concern in concerns)
    return hit, n_flags > 0, n_flags, n_correct, flag_lines, questions


def summarize(rows: list[EvalRow]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(row) for row in rows])
    records = []
    if frame.empty:
        return pd.DataFrame(records)
    for condition in CONDITIONS:
        group = frame[frame["condition"] == condition]
        if group.empty:
            continue
        records.append(_metrics_for(condition, group))
    return pd.DataFrame(records)


def summarize_by_operator(rows: list[EvalRow]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(row) for row in rows])
    records = []
    if frame.empty:
        return pd.DataFrame(records)
    bugs = frame[frame["kind"] == "bug"]
    if bugs.empty:
        return pd.DataFrame(records)
    for condition in CONDITIONS:
        for operator, group in bugs[bugs["condition"] == condition].groupby("operator", sort=True):
            recall = float(group["hit"].mean()) if len(group) else None
            records.append(
                {
                    "condition": condition,
                    "operator": operator,
                    "bugs": int(len(group)),
                    "recall": recall,
                }
            )
    return pd.DataFrame(records)


def _metrics_for(condition: str, group: pd.DataFrame) -> dict:
    bugs = group[group["kind"] == "bug"]
    clean = group[group["kind"] == "clean"]
    recall = float(bugs["hit"].mean()) if len(bugs) else None
    correct = int(group["n_correct_flags"].sum())
    total_flags = int(group["n_flags"].sum())
    precision = (correct / total_flags) if total_flags else None
    false_positive_rate = float(clean["flagged"].mean()) if len(clean) else None
    return {
        "condition": condition,
        "bugs": int(len(bugs)),
        "clean": int(len(clean)),
        "recall": recall,
        "precision": precision,
        "false_positive_rate": false_positive_rate,
        "f1": _f1(precision, recall),
        "mean_latency_s": float(group["latency_s"].mean()) if len(group) else None,
        "prompt_tokens": int(group["prompt_tokens"].fillna(0).sum()),
        "output_tokens": int(group["output_tokens"].fillna(0).sum()),
    }


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def estimate_cost(
    summary: pd.DataFrame,
    input_usd_per_million: float | None,
    output_usd_per_million: float | None,
) -> pd.DataFrame:
    if summary.empty or input_usd_per_million is None or output_usd_per_million is None:
        return summary
    priced = summary.copy()
    priced["estimated_usd"] = (
        priced["prompt_tokens"] * input_usd_per_million
        + priced["output_tokens"] * output_usd_per_million
    ) / 1_000_000
    return priced
