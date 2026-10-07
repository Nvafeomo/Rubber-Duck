from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from rubberduck import __version__
from rubberduck.diff import GitError, repo_root
from rubberduck.evaluate import discover_bugs, iter_jobs, planned_calls, review_bug
from rubberduck.llm import GeminiReviewer, ReviewError, load_env_file
from rubberduck.metrics import CONDITIONS, estimate_cost, summarize, summarize_by_operator
from rubberduck.models import EvalRow, Settings
from rubberduck.review import run_review
from rubberduck.textio import configure_stdio

_CORPUS_URL = "https://github.com/msiemens/tinydb"
_HELP = """
examples:
  rubberduck review --intent "fix the lookup key"
  rubberduck review --dry-run
  rubberduck seed --repo corpus/tinydb
  rubberduck fetch-corpus
  rubberduck eval --repo corpus/tinydb --max-per-class 40 --yes

The study target is 30 to 40 seeded bugs per class, plus a similar number of
untouched functions. A full run across all four conditions is hundreds of API
calls, so eval asks for --yes once that estimate passes 20.

Environment:
  GEMINI_API_KEY or GOOGLE_API_KEY   model access
  RUBBERDUCK_MODEL                    overrides the default Flash model
  RUBBERDUCK_FALLBACK_MODELS          comma-separated models to try if the main one is unavailable
  RUBBERDUCK_INTENT                   skip the intent prompt
  RUBBERDUCK_FORCE=1                  show concerns but allow the commit
"""


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    sys.exit(_dispatch(argv))


def _dispatch(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="rubberduck",
        description=(
            "Ask about subtle logic bugs in staged Python before the commit. "
            "One model call sees the diff, the numbered file, the developer's "
            "intent, and definitions pulled from other files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_HELP,
    )
    parser.add_argument("--version", action="version", version=f"rubberduck {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    review = commands.add_parser("review", help="Review staged Python files")
    review.add_argument("--repo", type=Path, default=None, help="Repository to review (default: current directory)")
    review.add_argument("--intent", default=None, help="What the change should do. Otherwise RubberDuck asks.")
    review.add_argument("--force", action="store_true", help="Print concerns and allow the commit")
    review.add_argument("--dry-run", action="store_true", help="Print the prompt and do not call the model")
    review.add_argument("--no-input", action="store_true", help="Do not prompt. Block the commit if there are concerns.")
    review.add_argument("--pass-on-error", action="store_true", help="Allow the commit when git or the model call fails")
    review.add_argument("--model", default=None, help="Gemini model id (default: gemini-3.8-flash or RUBBERDUCK_MODEL)")
    review.add_argument("--max-file-lines", type=int, default=400, help="Send only the enclosing function above this size")
    review.set_defaults(func=_cmd_review)

    seed = commands.add_parser("seed", help="List seeded bugs without calling the model")
    seed.add_argument("--repo", type=Path, required=True)
    seed.add_argument("--max-per-class", type=int, default=40)
    seed.add_argument("--seed", type=int, default=0)
    seed.add_argument("--include-tests", action="store_true")
    seed.set_defaults(func=_cmd_seed)

    evaluate = commands.add_parser("eval", help="Measure recall, precision, and false positives on seeded bugs")
    evaluate.add_argument("--repo", type=Path, required=True)
    evaluate.add_argument("--max-per-class", type=int, default=5, help="Bugs per class. The write-up target is 30 to 40.")
    evaluate.add_argument("--conditions", default=",".join(CONDITIONS))
    evaluate.add_argument("--output", type=Path, default=Path("rubberduck-eval.csv"))
    evaluate.add_argument("--seed", type=int, default=0)
    evaluate.add_argument("--include-tests", action="store_true")
    evaluate.add_argument("--no-clean", action="store_true", help="Skip untouched functions")
    evaluate.add_argument("--yes", action="store_true", help="Required when the run would make more than 20 calls")
    evaluate.add_argument("--model", default=None)
    evaluate.add_argument("--pause", type=float, default=0, help="Seconds to wait between calls")
    evaluate.add_argument("--input-usd-per-million", type=float, default=None)
    evaluate.add_argument("--output-usd-per-million", type=float, default=None)
    evaluate.set_defaults(func=_cmd_eval)

    fetch = commands.add_parser("fetch-corpus", help="Clone TinyDB into corpus/tinydb")
    fetch.add_argument("--dest", type=Path, default=Path("corpus") / "tinydb")
    fetch.set_defaults(func=_cmd_fetch)

    args = parser.parse_args(argv)
    return args.func(args)


def _cmd_review(args: argparse.Namespace) -> int:
    start = (args.repo or Path.cwd()).resolve()
    try:
        root = repo_root(start)
    except GitError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 0 if args.pass_on_error else 1
    load_env_file(root)
    settings = _settings(args.model, args.max_file_lines)
    client = None
    if not args.dry_run:
        try:
            client = GeminiReviewer(settings.model, settings.fallback_models)
        except ReviewError as exc:
            print(f"RubberDuck: {exc}", file=sys.stderr)
            return 0 if args.pass_on_error else 1
    return run_review(
        start,
        intent=args.intent,
        force=args.force,
        interactive=not args.no_input,
        dry_run=args.dry_run,
        client=client,
        settings=settings,
        pass_on_error=args.pass_on_error,
    )


def _cmd_seed(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"RubberDuck: {repo} is not a directory.", file=sys.stderr)
        return 1
    bugs = discover_bugs(
        repo,
        max_per_class=args.max_per_class,
        seed=args.seed,
        include_tests=args.include_tests,
    )
    if not bugs:
        print("No seedable functions found.")
        return 0
    for bug in bugs:
        print(
            f"{bug.operator}\t{bug.relpath}:{bug.absolute_line}\t"
            f"{bug.qualname}\t{bug.description}"
        )
    print(f"{len(bugs)} seeded bug(s).")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"RubberDuck: {repo} is not a directory.", file=sys.stderr)
        return 1
    conditions = [part.strip() for part in args.conditions.split(",") if part.strip()]
    try:
        bugs = discover_bugs(
            repo,
            max_per_class=args.max_per_class,
            seed=args.seed,
            include_tests=args.include_tests,
        )
    except OSError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 1
    if not bugs:
        print("No seedable functions found.")
        return 0
    calls = planned_calls(bugs, conditions, include_clean=not args.no_clean)
    print(f"{len(bugs)} seeded bug(s), {calls} model call(s), conditions: {', '.join(conditions)}.")
    if calls > 20 and not args.yes:
        print("Re-run with --yes to make those calls.")
        return 2
    load_env_file(repo)
    settings = _settings(args.model, 400)
    try:
        client = GeminiReviewer(settings.model, settings.fallback_models)
    except ReviewError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 1

    rows: list[EvalRow] = []
    try:
        for index, (condition, kind, bug) in enumerate(
            iter_jobs(bugs, conditions, include_clean=not args.no_clean),
            start=1,
        ):
            label = bug.operator if kind == "bug" else "clean"
            print(
                f"[{index}/{calls}] {condition} {label} {bug.relpath}:{bug.absolute_line}",
                flush=True,
            )
            try:
                rows.append(
                    review_bug(
                        bug,
                        kind=kind,
                        condition=condition,
                        repo=repo,
                        client=client,
                        settings=settings,
                    )
                )
            except ReviewError as exc:
                print(f"RubberDuck: {exc}", file=sys.stderr)
                _write_report(rows, args)
                return 1
            if args.pause:
                time.sleep(args.pause)
    except KeyboardInterrupt:
        print("\nStopped early. Writing the rows collected so far.")
    _write_report(rows, args)
    return 0 if rows else 1


def _cmd_fetch(args: argparse.Namespace) -> int:
    dest = args.dest
    if dest.exists():
        print(f"{dest} already exists.")
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {_CORPUS_URL} into {dest}")
    completed = subprocess.run(
        ["git", "clone", "--depth", "1", _CORPUS_URL, str(dest)],
        check=False,
    )
    return completed.returncode


def _write_report(rows: list[EvalRow], args: argparse.Namespace) -> None:
    if not rows:
        print("No rows to write.")
        return
    summary = summarize(rows)
    summary = estimate_cost(summary, args.input_usd_per_million, args.output_usd_per_million)
    by_operator = summarize_by_operator(rows)
    from dataclasses import asdict

    import pandas as pd

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(row) for row in rows]).to_csv(args.output, index=False)
    print()
    print(summary.to_string(index=False))
    if not by_operator.empty:
        print()
        print(by_operator.to_string(index=False))
    print(f"\nWrote {len(rows)} row(s) to {args.output}")


def _settings(model: str | None, max_file_lines: int) -> Settings:
    chosen = model or os.environ.get("RUBBERDUCK_MODEL") or Settings().model
    raw = os.environ.get("RUBBERDUCK_FALLBACK_MODELS", "")
    fallbacks = tuple(part.strip() for part in raw.split(",") if part.strip())
    return Settings(max_file_lines=max_file_lines, model=chosen, fallback_models=fallbacks)
