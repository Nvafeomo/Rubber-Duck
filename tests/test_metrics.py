import pytest

from rubberduck.metrics import file_matches, summarize
from rubberduck.models import EvalRow


def _row(**overrides) -> EvalRow:
    data = dict(
        condition="full",
        kind="bug",
        operator="variable_swap",
        file="app.py",
        function="build_record",
        bug_line=3,
        hit=False,
        flagged=False,
        n_flags=0,
        n_correct_flags=0,
        flag_lines="",
        questions="",
        latency_s=0.2,
        prompt_tokens=10,
        output_tokens=4,
        model="test",
    )
    data.update(overrides)
    return EvalRow(**data)


def test_file_match_accepts_suffix_and_basename():
    assert file_matches("", "pkg/app.py")
    assert file_matches("pkg/app.py", "pkg/app.py")
    assert file_matches("app.py", "pkg/app.py")
    assert file_matches("pkg\\app.py", "pkg/app.py")
    assert not file_matches("other.py", "pkg/app.py")


def test_summary_counts_exact_line_hits():
    rows = [
        _row(hit=True, flagged=True, n_flags=2, n_correct_flags=1, flag_lines="3;9"),
        _row(kind="bug", hit=False, n_flags=0, n_correct_flags=0, operator="dict_key_swap"),
        _row(kind="clean", operator="", bug_line=None, flagged=True, n_flags=1, n_correct_flags=0),
        _row(kind="clean", operator="", bug_line=None, flagged=False, n_flags=0, n_correct_flags=0),
    ]
    summary = summarize(rows)
    full = summary[summary["condition"] == "full"].iloc[0]
    assert full["bugs"] == 2
    assert full["clean"] == 2
    assert full["recall"] == pytest.approx(0.5)
    assert full["precision"] == pytest.approx(1 / 3)
    assert full["false_positive_rate"] == pytest.approx(0.5)
    assert full["f1"] == pytest.approx(0.4)
    assert full["prompt_tokens"] == 40
