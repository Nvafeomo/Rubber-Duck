import pytest

from rubberduck.llm import GeminiReviewer, ReviewError, is_transient


class _ApiError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"{code} {message}")
        self.code = code


class _Response:
    text = '{"concerns": [{"file": "a.py", "line": 3, "question": "key?"}]}'
    usage_metadata = None


def _reviewer(monkeypatch, outcomes, fallbacks=()):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    sleeps: list[float] = []
    reviewer = GeminiReviewer("main-model", fallbacks, retry_delays=(1.0, 2.0), sleep=sleeps.append)
    calls: list[str] = []

    def generate_content(model, contents, config):
        calls.append(model)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    reviewer._client.models.generate_content = generate_content
    return reviewer, calls, sleeps


def test_retries_transient_error_then_succeeds(monkeypatch):
    reviewer, calls, sleeps = _reviewer(
        monkeypatch, [_ApiError(503, "UNAVAILABLE"), _Response()]
    )
    completion = reviewer.complete("prompt")
    assert [c.line for c in completion.concerns] == [3]
    assert calls == ["main-model", "main-model"]
    assert sleeps == [1.0]


def test_switches_to_fallback_after_retries(monkeypatch):
    busy = [_ApiError(503, "UNAVAILABLE") for _ in range(3)]
    reviewer, calls, sleeps = _reviewer(monkeypatch, [*busy, _Response()], fallbacks=("backup",))
    reviewer.complete("prompt")
    assert calls == ["main-model"] * 3 + ["backup"]
    assert sleeps == [1.0, 2.0]


def test_gives_up_with_clear_message(monkeypatch):
    reviewer, calls, _ = _reviewer(monkeypatch, [_ApiError(429, "RESOURCE_EXHAUSTED")] * 3)
    with pytest.raises(ReviewError, match="stayed unavailable"):
        reviewer.complete("prompt")
    assert len(calls) == 3


def test_does_not_retry_permanent_error(monkeypatch):
    reviewer, calls, sleeps = _reviewer(monkeypatch, [_ApiError(400, "INVALID_ARGUMENT bad key")])
    with pytest.raises(ReviewError, match="INVALID_ARGUMENT"):
        reviewer.complete("prompt")
    assert calls == ["main-model"]
    assert sleeps == []


class ReadTimeout(Exception):
    pass


def test_is_transient():
    assert is_transient(_ApiError(503, "UNAVAILABLE"))
    assert is_transient(TimeoutError())
    assert is_transient(ReadTimeout("[WinError 10060] host has failed to respond"))
    assert not is_transient(_ApiError(404, "NOT_FOUND"))
