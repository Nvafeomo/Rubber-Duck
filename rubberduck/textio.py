from __future__ import annotations

import sys


def without_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def configure_stdio() -> None:
    """Keep a review from aborting when the console cannot encode a source character."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            continue
