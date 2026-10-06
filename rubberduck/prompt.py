from __future__ import annotations

INSTRUCTIONS = """You are RubberDuck, a pre-commit reviewer for subtle logic bugs.

The code under review is syntactically valid. Ask a question only when a changed line is inconsistent with the developer intent or with a related definition. The inconsistencies that matter are:
- a wrong variable
- a wrong dictionary key
- a loop iterating over the wrong collection

Rules:
- If the change fits the intent, return an empty concerns list.
- Do not declare code wrong. Phrase each concern as a short question the developer can confirm or dismiss.
- Cite the file path given below and the exact line number from the left margin of the numbered source. Ignore numbers in the diff.
- Ask about one specific line. Return at most three concerns.
- Do not comment on style, formatting, type hints, missing tests, or speculative design.
"""


def build_prompt(
    *,
    relpath: str,
    diff: str,
    numbered_source: str,
    focus: str,
    intent: str | None,
    context: str | None,
) -> str:
    """Assemble the single review request.

    ``intent`` or ``context`` set to None drops that section. The evaluation
    uses that to compare the full review with the same call minus intent,
    minus cross-file context, or minus both.
    """
    parts = [INSTRUCTIONS.strip(), f"File: {relpath}", f"Lines to inspect: {focus}"]
    if intent is not None:
        text = intent.strip() or "(none given)"
        parts.append(f"Developer intent:\n{text}")
    parts.append(f"Staged change:\n{diff.strip() or '(no textual diff)'}")
    parts.append(
        "Numbered source (cite these line numbers):\n"
        f"{numbered_source or '(empty file)'}"
    )
    if context:
        parts.append(f"Related definitions from other files:\n{context}")
    parts.append(
        'Return JSON: {"concerns": [{"file": string, "line": integer, "question": string}]}'
    )
    return "\n\n".join(parts)


def focus_label(changed: set[int]) -> str:
    if not changed:
        return "(none marked; read the staged change)"
    ordered = sorted(changed)
    if len(ordered) > 40:
        head = ", ".join(str(number) for number in ordered[:40])
        return f"{head}, ... ({len(ordered)} lines)"
    return ", ".join(str(number) for number in ordered)
