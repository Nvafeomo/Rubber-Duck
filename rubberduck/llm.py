from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Protocol, TypedDict

from rubberduck.models import Completion, Concern, Usage


class ConcernSchema(TypedDict):
    file: str
    line: int
    question: str


class ReviewSchema(TypedDict):
    concerns: list[ConcernSchema]


class Reviewer(Protocol):
    def complete(self, prompt: str) -> Completion:
        """Send one review request and return parsed concerns plus token usage."""


class ReviewError(RuntimeError):
    pass


def load_env_file(repo: Path) -> None:
    """Fill in unset variables from a repo-local ``.env`` without overriding the environment."""
    path = repo / ".env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


class GeminiReviewer:
    """One generateContent call. Retrieval stays outside the model."""

    def __init__(self, model: str) -> None:
        self.model = model
        key = api_key()
        if not key:
            raise ReviewError(
                "Set GEMINI_API_KEY or GOOGLE_API_KEY before running a review."
            )
        try:
            from google import genai
        except ImportError as exc:
            raise ReviewError(
                "The google-genai package is not installed. Run: pip install -e ."
            ) from exc
        self._client = genai.Client(api_key=key)

    def complete(self, prompt: str) -> Completion:
        from google.genai import types

        config_kwargs: dict = {
            "temperature": 0,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json",
            "response_schema": ReviewSchema,
        }
        if _model_major(self.model) >= 3:
            thinking = getattr(types, "ThinkingConfig", None)
            if thinking is not None:
                config_kwargs["thinking_config"] = thinking(thinking_level="MINIMAL")
        response, latency = self._generate(prompt, config_kwargs)
        text = getattr(response, "text", None) or ""
        if not text:
            raise ReviewError("The model returned an empty response.")
        usage_meta = getattr(response, "usage_metadata", None)
        usage = Usage(
            latency_s=latency,
            prompt_tokens=_meta_int(usage_meta, "prompt_token_count"),
            output_tokens=_meta_int(usage_meta, "candidates_token_count"),
        )
        return Completion(concerns=parse_concerns(text), usage=usage)

    def _generate(self, prompt: str, config_kwargs: dict):
        from google.genai import types

        try:
            config = types.GenerateContentConfig(**config_kwargs)
        except TypeError:
            reduced = {key: value for key, value in config_kwargs.items() if key != "thinking_config"}
            config = types.GenerateContentConfig(**reduced)
        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            if "thinking_config" in config_kwargs and "thinking" in str(exc).lower():
                reduced = {key: value for key, value in config_kwargs.items() if key != "thinking_config"}
                return self._generate(prompt, reduced)
            raise ReviewError(str(exc)) from exc
        return response, time.perf_counter() - started


def parse_concerns(payload: str) -> list[Concern]:
    text = payload.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReviewError(f"Model response was not JSON: {exc}") from exc
    if isinstance(data, dict):
        items = data.get("concerns", [])
    elif isinstance(data, list):
        items = data
    else:
        raise ReviewError("Model response was not a concerns object.")
    if not isinstance(items, list):
        raise ReviewError("Model response concerns field was not a list.")

    concerns: list[Concern] = []
    seen: set[tuple[str, int, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        line = _as_int(item.get("line"))
        question = str(item.get("question", "")).strip()
        file_name = str(item.get("file", "")).strip().replace("\\", "/")
        if line is None or line < 1 or not question:
            continue
        key = (file_name, line, question)
        if key in seen:
            continue
        seen.add(key)
        concerns.append(Concern(file=file_name, line=line, question=question))
        if len(concerns) == 3:
            break
    return concerns


def _model_major(model: str) -> int:
    marker = "gemini-"
    if marker not in model:
        return 0
    rest = model.split(marker, 1)[1]
    digits = []
    for char in rest:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return int("".join(digits)) if digits else 0


def _meta_int(meta: object, name: str) -> int | None:
    if meta is None:
        return None
    value = getattr(meta, name, None)
    if isinstance(value, int):
        return value
    return None


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
