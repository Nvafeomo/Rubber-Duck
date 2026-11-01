"""``rubberduck skills ...`` commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rubberduck.llm import GeminiReviewer, ReviewError, load_env_file

_HELP = """
examples:
  rubberduck skills facts path/to/skill
  rubberduck skills audit path/to/skill --dry-run
  rubberduck skills audit path/to/skill
  rubberduck skills collect https://github.com/OWNER/REPO
  rubberduck skills status
  rubberduck skills seed
  rubberduck skills suggest-divergence CASE_ID --model gemini-2.5-pro
  rubberduck skills eval --pause 4 --yes
"""


def register(commands) -> None:
    skills = commands.add_parser("skills", help="Check agent skills for intent-behavior misalignment",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=_HELP)
    sub = skills.add_subparsers(dest="skills_command", required=True)

    facts = sub.add_parser("facts", help="Print claims and static facts for a skill (no model call)")
    facts.add_argument("path", type=Path)
    facts.set_defaults(func=_cmd_facts)

    audit = sub.add_parser("audit", help="Audit one skill")
    audit.add_argument("path", type=Path)
    audit.add_argument("--condition", default="full", choices=["full", "no_facts", "single_file", "rules", "similarity"])
    audit.add_argument("--dry-run", action="store_true", help="Print the prompt and do not call the model")
    audit.add_argument("--json", type=Path, default=None, help="Also write the result as JSON")
    audit.add_argument("--model", default=None)
    audit.set_defaults(func=_cmd_audit)

    collect = sub.add_parser("collect", help="Copy skills from repos or local folders into the benchmark as drafts")
    collect.add_argument("repos", nargs="+", help="GitHub URLs or local folders")
    collect.add_argument("--bench", type=Path, default=Path("benchmark"))
    collect.add_argument("--cache", type=Path, default=Path(".cache") / "skill-repos")
    collect.add_argument("--all-languages", action="store_true", help="Keep skills with only shell or JS scripts too")
    collect.add_argument("--limit", type=int, default=None, help="At most this many skills per repo")
    collect.set_defaults(func=_cmd_collect)

    status = sub.add_parser("status", help="Count cases and check labels")
    status.add_argument("--bench", type=Path, default=Path("benchmark"))
    status.set_defaults(func=_cmd_status)

    seed = sub.add_parser("seed", help="Plant misalignments in verified aligned cases")
    seed.add_argument("--bench", type=Path, default=Path("benchmark"))
    seed.add_argument("--variants", default=None, help="Comma-separated subset (default: all)")
    seed.add_argument("--seed", type=int, default=0)
    seed.set_defaults(func=_cmd_seed)

    draft = sub.add_parser("suggest-divergence", help="Have a model draft divergent edits of a clean case for you to review")
    draft.add_argument("case", help="Case id under benchmark/cases (must be verified aligned)")
    draft.add_argument("--bench", type=Path, default=Path("benchmark"))
    draft.add_argument("-n", type=int, default=4, help="How many edits to ask for")
    draft.add_argument("--model", default=None, help="Use a different model than the one you audit with")
    draft.add_argument("--dry-run", action="store_true", help="Print the prompt only")
    draft.set_defaults(func=_cmd_suggest)

    evaluate = sub.add_parser("eval", help="Run methods over the benchmark and score them")
    evaluate.add_argument("--bench", type=Path, default=Path("benchmark"))
    evaluate.add_argument("--methods", default="full,no_facts,single_file,rules,similarity")
    evaluate.add_argument("--out", type=Path, default=Path("results") / "skills")
    evaluate.add_argument("--name", default="skills-eval")
    evaluate.add_argument("--include-drafts", action="store_true", help="Also score unverified labels (for trying things out)")
    evaluate.add_argument("--only", default=None, help="Only cases whose id contains this text")
    evaluate.add_argument("--pause", type=float, default=0.0, help="Seconds between model calls")
    evaluate.add_argument("--tolerance", type=int, default=3, help="Lines a finding may be off and still count")
    evaluate.add_argument("--model", default=None)
    evaluate.add_argument("--yes", action="store_true", help="Required when the run makes more than 20 model calls")
    evaluate.set_defaults(func=_cmd_eval)


def _cmd_facts(args: argparse.Namespace) -> int:
    from rubberduck.skills.behaviors import analyze_skill, format_facts
    from rubberduck.skills.claims import extract_claims, format_claims
    from rubberduck.skills.loader import load_skill

    skill = load_skill(args.path)
    print(f"Skill: {skill.name}")
    print(f"Docs: {', '.join(d.relpath for d in skill.docs) or '(none)'}")
    print(f"Scripts: {', '.join(s.relpath for s in skill.scripts) or '(none)'}")
    print("\nClaims:\n" + format_claims(extract_claims(skill)))
    print("\n" + format_facts(analyze_skill(skill)))
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from rubberduck.skills.audit import audit_skill, format_findings
    from rubberduck.skills.baselines import BASELINES, run_baseline
    from rubberduck.skills.loader import load_skill

    skill = load_skill(args.path)
    if args.condition in BASELINES:
        result = run_baseline(args.condition, skill)
    else:
        model = None if args.dry_run else _model(args.model)
        if model is False:
            return 1
        result, prompt = audit_skill(skill, model or None, condition=args.condition)
        if result is None:
            print(prompt)
            print(f"\n(dry run: {len(prompt)} characters, no model call)")
            return 0
    print(format_findings(result))
    print(f"\n{result.usage.latency_s:.2f}s, prompt tokens {result.usage.prompt_tokens}, files in prompt {result.files_in_prompt}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(result.to_json() + "\n", encoding="utf-8")
    return 0


def _cmd_collect(args: argparse.Namespace) -> int:
    from rubberduck.skills.benchmark import collect

    total = 0
    for repo in args.repos:
        try:
            created = collect(repo, args.bench, args.cache, python_only=not args.all_languages, limit=args.limit)
        except Exception as exc:  # a bad repo should not stop the others
            print(f"{repo}: failed ({exc})", file=sys.stderr)
            continue
        total += len(created)
        print(f"{repo}: {len(created)} new draft case(s)")
        for case_id in created:
            print(f"  {case_id}")
    print(f"\n{total} draft case(s) added under {args.bench / 'cases'}. Label them, then set status to \"verified\".")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    from rubberduck.skills.benchmark import LABEL_FILE, validate_label

    counts = {"draft": 0, "verified": 0}
    origins: dict[str, int] = {}
    aligned = 0
    types: dict[str, int] = {}
    problems = 0
    for path in sorted((args.bench / "cases").glob(f"*/{LABEL_FILE}")):
        data = json.loads(path.read_text(encoding="utf-8"))
        status = data.get("status", "draft")
        counts[status] = counts.get(status, 0) + 1
        if status != "verified":
            continue
        origins[data.get("origin", "real")] = origins.get(data.get("origin", "real"), 0) + 1
        aligned += bool(data.get("aligned"))
        for item in data.get("misalignments", []):
            types[item.get("type", "?")] = types.get(item.get("type", "?"), 0) + 1
        for problem in validate_label(data):
            problems += 1
            print(f"{path.parent.name}: {problem}")
    print(f"cases: {counts.get('verified', 0)} verified, {counts.get('draft', 0)} draft")
    print(f"verified by origin: {origins}")
    print(f"verified aligned: {aligned}")
    print(f"labeled misalignments: {types}")
    return 1 if problems else 0


def _cmd_seed(args: argparse.Namespace) -> int:
    from rubberduck.skills.benchmark import load_cases
    from rubberduck.skills.seed import ALL_VARIANTS, VARIANTS, seed_case

    variants = tuple(v.strip() for v in args.variants.split(",")) if args.variants else VARIANTS
    unknown = [v for v in variants if v not in ALL_VARIANTS]
    if unknown:
        print(f"Unknown variants: {', '.join(unknown)}. Choose from {', '.join(ALL_VARIANTS)}", file=sys.stderr)
        return 1
    bases = [case for case in load_cases(args.bench) if case.origin == "real" and case.aligned]
    if not bases:
        print("No verified aligned real cases to seed. Label some skills first.")
        return 1
    made = 0
    for case in bases:
        for case_id, outcome in seed_case(case, args.bench, variants, args.seed):
            print(f"{case_id}: {outcome}")
            made += outcome in ALL_VARIANTS
    print(f"\n{made} seeded case(s) written.")
    return 0


def _cmd_suggest(args: argparse.Namespace) -> int:
    from rubberduck.skills.benchmark import load_cases
    from rubberduck.skills.suggest import build_suggest_prompt, suggest

    case = next((c for c in load_cases(args.bench, include_drafts=True) if c.id == args.case), None)
    if case is None:
        print(f"No case {args.case!r} in {args.bench / 'cases'}", file=sys.stderr)
        return 1
    if not (case.aligned and case.status == "verified" and case.origin == "real"):
        print("Only verified aligned real cases can be used. Label it first.", file=sys.stderr)
        return 1
    if args.dry_run:
        print(build_suggest_prompt(case, args.n))
        return 0
    model = _model(args.model)
    if model is False:
        return 1
    try:
        results = suggest(case, args.bench, model, args.n)
    except ReviewError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 1
    for name, status in results:
        print(f"{name}: {status}")
    print("\nOpen each new label.json, check the edit under \"review\", then set status to verified or delete the folder.")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from rubberduck.skills.baselines import BASELINES
    from rubberduck.skills.benchmark import load_cases
    from rubberduck.skills.evaluate import METHODS, run, summarize, summarize_by_variant, write_summary

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    unknown = [m for m in methods if m not in METHODS]
    if unknown:
        print(f"Unknown methods: {', '.join(unknown)}. Choose from {', '.join(METHODS)}", file=sys.stderr)
        return 1
    try:
        cases = load_cases(args.bench, include_drafts=args.include_drafts)
    except ValueError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 1
    if args.only:
        cases = [case for case in cases if args.only in case.id]
    if not cases:
        print("No cases to score. Verify some labels, or pass --include-drafts to try things out.")
        return 1
    llm_methods = [m for m in methods if m not in BASELINES]
    calls = len(cases) * len(llm_methods)
    print(f"{len(cases)} case(s), methods: {', '.join(methods)}, {calls} model call(s).")
    if calls > 20 and not args.yes:
        print("Re-run with --yes to make those calls.")
        return 2
    model = _model(args.model) if llm_methods else None
    if model is False:
        return 1
    try:
        frame = run(cases, methods, model, args.out, pause_s=args.pause, tolerance=args.tolerance)
    except KeyboardInterrupt:
        print("\nStopped early.")
        return 1
    rows_path, summary_path = write_summary(frame, args.out, args.name)
    print()
    print(summarize(frame).to_string(index=False))
    print()
    print(summarize_by_variant(frame).to_string(index=False))
    print(f"\nWrote {rows_path} and {summary_path}")
    return 0


def _model(name: str | None):
    import os

    from rubberduck.models import Settings

    load_env_file(Path.cwd())
    chosen = name or os.environ.get("RUBBERDUCK_MODEL") or Settings().model
    fallbacks = tuple(p.strip() for p in os.environ.get("RUBBERDUCK_FALLBACK_MODELS", "").split(",") if p.strip())
    try:
        return GeminiReviewer(chosen, fallbacks)
    except ReviewError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return False
