from __future__ import annotations

import os
import sys
from pathlib import Path

from rubberduck.context import format_snippets, related_snippets
from rubberduck.diff import GitError, load_staged_python, repo_root
from rubberduck.llm import ReviewError, Reviewer
from rubberduck.models import Concern, Settings, StagedFile
from rubberduck.prompt import build_prompt, focus_label
from rubberduck.sourceview import select_view


def run_review(
    start: Path,
    *,
    intent: str | None,
    force: bool,
    interactive: bool,
    dry_run: bool,
    client: Reviewer | None,
    settings: Settings,
    pass_on_error: bool,
) -> int:
    try:
        repo = repo_root(start)
        staged = load_staged_python(repo)
    except GitError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 0 if pass_on_error else 1

    if not staged:
        return 0

    intent_text = intent if intent is not None else _read_intent(interactive)
    prompts = [
        (item, _prompt_for(repo, item, intent_text, settings, include_context=True))
        for item in staged
    ]
    if dry_run:
        for item, prompt in prompts:
            print(f"--- {item.path} ---")
            print(prompt)
            print()
        return 0

    if client is None:
        print("RubberDuck: no reviewer was configured.", file=sys.stderr)
        return 0 if pass_on_error else 1

    concerns: list[Concern] = []
    try:
        for _item, prompt in prompts:
            concerns.extend(client.complete(prompt).concerns)
    except ReviewError as exc:
        print(f"RubberDuck: {exc}", file=sys.stderr)
        return 0 if pass_on_error else 1

    if not concerns:
        noun = "file" if len(staged) == 1 else "files"
        print(f"RubberDuck: no concerns in {len(staged)} {noun}.")
        return 0

    print("RubberDuck:")
    print(format_concerns(concerns))
    if force or _force_enabled():
        print("Force set; allowing the commit.")
        return 0
    if not interactive:
        print("Commit blocked. Set RUBBERDUCK_FORCE=1, or use git commit --no-verify.")
        return 1
    if _dismissed():
        print("Concerns dismissed; allowing the commit.")
        return 0
    print("Commit blocked.")
    return 1


def format_concerns(concerns: list[Concern]) -> str:
    blocks = []
    for index, concern in enumerate(concerns, start=1):
        location = f"{concern.file}:{concern.line}" if concern.file else f"line {concern.line}"
        blocks.append(f"{index}. {location}\n   {concern.question}")
    return "\n".join(blocks)


def _prompt_for(
    repo: Path,
    staged: StagedFile,
    intent: str | None,
    settings: Settings,
    include_context: bool,
) -> str:
    numbered = select_view(
        staged.source,
        staged.changed_lines,
        settings.max_file_lines,
        settings.max_scope_lines,
    )
    context = None
    if include_context and staged.changed_lines:
        snippets = related_snippets(
            staged.source,
            repo / staged.path,
            staged.changed_lines,
            repo,
            settings,
        )
        rendered = format_snippets(snippets)
        context = rendered or None
    return build_prompt(
        relpath=staged.path,
        diff=staged.diff,
        numbered_source=numbered,
        focus=focus_label(staged.changed_lines),
        intent=intent,
        context=context,
    )


def _read_intent(interactive: bool) -> str:
    preset = os.environ.get("RUBBERDUCK_INTENT")
    if preset is not None:
        return preset
    if not interactive:
        return ""
    try:
        if os.name == "nt":
            with open("CONOUT$", "w", encoding="utf-8", errors="replace") as output, open(
                "CONIN$", "r", encoding="utf-8", errors="replace"
            ) as console:
                output.write("RubberDuck: what should this change do?\n> ")
                output.flush()
                return console.readline().strip()
        with open("/dev/tty", "r+", encoding="utf-8", errors="replace") as console:
            console.write("RubberDuck: what should this change do?\n> ")
            console.flush()
            return console.readline().strip()
    except OSError:
        return ""


def _dismissed() -> bool:
    try:
        if os.name == "nt":
            with open("CONOUT$", "w", encoding="utf-8", errors="replace") as output, open(
                "CONIN$", "r", encoding="utf-8", errors="replace"
            ) as console:
                output.write("[a]bort  [d]ismiss and commit: ")
                output.flush()
                answer = console.readline()
        else:
            with open("/dev/tty", "r+", encoding="utf-8", errors="replace") as console:
                console.write("[a]bort  [d]ismiss and commit: ")
                console.flush()
                answer = console.readline()
    except OSError:
        return False
    return answer.strip().lower() in {"d", "dismiss"}


def _force_enabled() -> bool:
    return os.environ.get("RUBBERDUCK_FORCE", "").strip().lower() in {"1", "true", "yes"}
