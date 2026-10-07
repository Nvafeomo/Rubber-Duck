from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Protocol, TypedDict

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


class TransientReviewError(ReviewError):
    """A model call failed in a way that is worth retrying (overload, rate limit, timeout)."""


_TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}
_TRANSIENT_MARKERS = ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "overloaded", "timed out")
_NETWORK_ERRORS = ("Timeout", "TransportError", "NetworkError", "ConnectError")
_RETRY_DELAYS_S = (2.0, 5.0)
_TIMEOUT_MS = 30_000


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
    """One generateContent call. Retrieval stays outside the model.

    Temporary failures (503 UNAVAILABLE, 429, timeouts) are retried with a short
    backoff, then each fallback model is tried in turn.
    """

    def __init__(
        self,
        model: str,
        fallbacks: tuple[str, ...] = (),
        retry_delays: tuple[float, ...] = _RETRY_DELAYS_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self.fallbacks = tuple(name for name in fallbacks if name and name != model)
        self._retry_delays = retry_delays
        self._sleep = sleep
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
        try:
            self._client = genai.Client(
                api_key=key,
                http_options=genai.types.HttpOptions(timeout=_TIMEOUT_MS),
            )
        except (AttributeError, TypeError):
            self._client = genai.Client(api_key=key)

    def complete(self, prompt: str) -> Completion:
        models = (self.model, *self.fallbacks)
        last: TransientReviewError | None = None
        for index, model in enumerate(models):
            if index:
                _notice(f"switching to fallback model {model}.")
            for attempt in range(len(self._retry_delays) + 1):
                try:
                    return self._complete_with(model, prompt)
                except TransientReviewError as exc:
                    last = exc
                    if attempt < len(self._retry_delays):
                        delay = self._retry_delays[attempt]
                        _notice(f"{model} is temporarily unavailable; retrying in {delay:g}s.")
                        self._sleep(delay)
        raise ReviewError(
            f"Gemini stayed unavailable after retries ({', '.join(models)}). "
            f"Wait a minute and run git commit again. Last error: {last}"
        )

    def _complete_with(self, model: str, prompt: str) -> Completion:
        from google.genai import types

        config_kwargs: dict = {
            "temperature": 0,
            "max_output_tokens": 1024,
            "response_mime_type": "application/json",
            "response_schema": ReviewSchema,
        }
        if _model_major(model) >= 3:
            thinking = getattr(types, "ThinkingConfig", None)
            if thinking is not None:
                config_kwargs["thinking_config"] = thinking(thinking_level="MINIMAL")
        response, latency = self._generate(model, prompt, config_kwargs)
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

    def _generate(self, model: str, prompt: str, config_kwargs: dict):
        from google.genai import types

        try:
            config = types.GenerateContentConfig(**config_kwargs)
        except TypeError:
            reduced = {key: value for key, value in config_kwargs.items() if key != "thinking_config"}
            config = types.GenerateContentConfig(**reduced)
        started = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            if "thinking_config" in config_kwargs and "thinking" in str(exc).lower():
                reduced = {key: value for key, value in config_kwargs.items() if key != "thinking_config"}
                return self._generate(model, prompt, reduced)
            if is_transient(exc):
                raise TransientReviewError(str(exc)) from exc
            raise ReviewError(str(exc)) from exc
        return response, time.perf_counter() - started


def is_transient(exc: BaseException) -> bool:
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in _TRANSIENT_CODES:
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    # httpx/httpcore network failures do not subclass the builtin errors.
    if any(marker in cls.__name__ for cls in type(exc).__mro__ for marker in _NETWORK_ERRORS):
        return True
    text = str(exc)
    return any(marker.lower() in text.lower() for marker in _TRANSIENT_MARKERS)


def _notice(message: str) -> None:
    print(f"RubberDuck: {message}", file=sys.stderr, flush=True)


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
