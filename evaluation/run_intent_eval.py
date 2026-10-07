"""Run RubberDuck on the intent-sensitive benchmark, with and without intent.

Every case is reviewed as a brand-new staged file (the situation in the live
demo), so the model never sees an "original" line to compare against. Each
case runs twice per condition: the buggy version and the clean version.

Usage, from the project root:
    .venv\\Scripts\\python.exe -m evaluation.run_intent_eval --pause 4
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from rubberduck.cli import _settings
from rubberduck.llm import GeminiReviewer, ReviewError, load_env_file
from rubberduck.prompt import build_prompt, focus_label
from rubberduck.sourceview import select_view

from evaluation.intent_cases import CASES, bug_line_number, buggy_source

CONDITIONS = ("with-intent", "code-only")


def new_file_diff(relpath: str, source: str) -> str:
    lines = source.splitlines()
    header = (
        f"diff --git a/{relpath} b/{relpath}\nnew file mode 100644\n"
        f"--- /dev/null\n+++ b/{relpath}\n@@ -0,0 +1,{len(lines)} @@\n"
    )
    return header + "\n".join("+" + line for line in lines)


def build_case_prompt(case, source: str, include_intent: bool, settings) -> str:
    relpath = f"{case.name}.py"
    changed = set(range(1, len(source.splitlines()) + 1))
    return build_prompt(
        relpath=relpath,
        diff=new_file_diff(relpath, source),
        numbered_source=select_view(source, changed, settings.max_file_lines, settings.max_scope_lines),
        focus=focus_label(changed),
        intent=case.intent if include_intent else None,
        context=None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=Path("results") / "intent-eval-results.csv")
    parser.add_argument("--pause", type=float, default=4.0, help="Seconds between calls (free-tier rate limit)")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)

    load_env_file(Path.cwd())
    settings = _settings(args.model, 400)
    try:
        client = GeminiReviewer(settings.model, settings.fallback_models)
    except ReviewError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 1

    jobs = [(cond, case, kind) for cond in CONDITIONS for case in CASES for kind in ("bug", "clean")]
    rows = []
    for index, (condition, case, kind) in enumerate(jobs, start=1):
        source = buggy_source(case) if kind == "bug" else case.clean
        prompt = build_case_prompt(case, source, condition == "with-intent", settings)
        print(f"[{index}/{len(jobs)}] {condition} {kind} {case.name}", flush=True)
        try:
            completion = client.complete(prompt)
        except ReviewError as exc:
            print(f"RubberDuck: {exc}", file=sys.stderr)
            break
        bug_line = bug_line_number(case)
        flags = [c.line for c in completion.concerns]
        correct = sum(1 for line in flags if kind == "bug" and line == bug_line)
        rows.append({
            "condition": condition,
            "case": case.name,
            "bug_type": case.bug_type,
            "kind": kind,
            "bug_line": bug_line,
            "hit": kind == "bug" and correct > 0,
            "flagged": bool(flags),
            "n_flags": len(flags),
            "n_correct_flags": correct,
            "flag_lines": ";".join(map(str, flags)),
            "questions": " | ".join(c.question for c in completion.concerns),
            "latency_s": round(completion.usage.latency_s, 3),
            "model": settings.model,
        })
        if args.pause and index < len(jobs):
            time.sleep(args.pause)

    if not rows:
        print("No rows collected.")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print_summary(rows)
    print(f"\nWrote {len(rows)} row(s) to {args.output}")
    return 0


def print_summary(rows: list[dict]) -> None:
    print("\nBy condition")
    print(f"{'condition':<12} {'caught':>8} {'precision':>10} {'clean flagged':>14} {'avg latency':>12}")
    for condition in CONDITIONS:
        group = [r for r in rows if r["condition"] == condition]
        if not group:
            continue
        bugs = [r for r in group if r["kind"] == "bug"]
        clean = [r for r in group if r["kind"] == "clean"]
        hits = sum(r["hit"] for r in bugs)
        flags = sum(r["n_flags"] for r in group)
        correct = sum(r["n_correct_flags"] for r in group)
        precision = f"{correct / flags:.2f}" if flags else "n/a"
        flagged = sum(r["flagged"] for r in clean)
        latency = sum(r["latency_s"] for r in group) / len(group)
        print(f"{condition:<12} {hits:>5}/{len(bugs):<2} {precision:>10} {flagged:>11}/{len(clean):<2} {latency:>10.2f} s")
    print("\nBugs caught by type")
    types = sorted({r["bug_type"] for r in rows})
    print(f"{'bug type':<24} " + " ".join(f"{c:>12}" for c in CONDITIONS))
    for bug_type in types:
        cells = []
        for condition in CONDITIONS:
            bugs = [r for r in rows if r["condition"] == condition and r["kind"] == "bug" and r["bug_type"] == bug_type]
            cells.append(f"{sum(r['hit'] for r in bugs)}/{len(bugs)}" if bugs else "-")
        print(f"{bug_type:<24} " + " ".join(f"{c:>12}" for c in cells))


if __name__ == "__main__":
    sys.exit(main())
