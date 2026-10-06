import re
import shutil
from pathlib import Path

import pytest

from rubberduck.cli import main
from rubberduck.evaluate import discover_bugs, review_bug
from rubberduck.llm import Completion, Usage
from rubberduck.metrics import summarize
from rubberduck.models import Concern, Settings

APP = '''\
from samplelib.models import label

def build_record(items, other):
    """Save a record under its name and total the items."""
    row = {"name": label(items[0]), "id": other}
    total = 0
    for value in items:
        total += value
    return row["name"], total
'''


class FlagWhenIntent:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt: str) -> Completion:
        self.prompts.append(prompt)
        if "Developer intent:" not in prompt:
            return Completion([], Usage(0.01, 3, 1))
        match = re.search(r"Line (\d+):", prompt)
        if not match:
            return Completion([], Usage(0.01, 3, 1))
        file_match = re.search(r"File: (\S+)", prompt)
        concern = Concern(
            file=file_match.group(1),
            line=int(match.group(1)),
            question="Did you mean the other name?",
        )
        return Completion([concern], Usage(0.01, 3, 1))


def _corpus(tmp_path: Path) -> Path:
    package = tmp_path / "samplelib"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "models.py").write_text(
        "def label(value):\n    return str(value)\n",
        encoding="utf-8",
    )
    (package / "app.py").write_text(APP, encoding="utf-8")
    return tmp_path


def test_discover_edits_the_reported_line(tmp_path: Path):
    bugs = discover_bugs(_corpus(tmp_path), max_per_class=5, seed=0, include_tests=False)
    assert {bug.operator for bug in bugs} == {
        "variable_swap",
        "dict_key_swap",
        "loop_iterable_swap",
    }
    for bug in bugs:
        original = bug.file_source.splitlines()[bug.absolute_line - 1]
        mutated = bug.mutated_source.splitlines()[bug.absolute_line - 1]
        assert original != mutated


def test_conditions_change_what_the_prompt_contains_and_what_counts_as_a_hit(tmp_path: Path):
    repo = _corpus(tmp_path)
    bugs = discover_bugs(repo, max_per_class=5, seed=0, include_tests=False)
    client = FlagWhenIntent()
    settings = Settings()
    rows = []
    for condition in ("full", "code-only", "intent-only", "context-only"):
        for bug in bugs:
            rows.append(
                review_bug(
                    bug,
                    kind="bug",
                    condition=condition,
                    repo=repo,
                    client=client,
                    settings=settings,
                )
            )
        rows.append(
            review_bug(
                bugs[0],
                kind="clean",
                condition=condition,
                repo=repo,
                client=client,
                settings=settings,
            )
        )

    summary = summarize(rows)
    by_condition = {row.condition: row for row in summary.itertuples(index=False)}
    assert by_condition["full"].recall == pytest.approx(1)
    assert by_condition["intent-only"].recall == pytest.approx(1)
    assert by_condition["code-only"].recall == pytest.approx(0)
    assert by_condition["context-only"].recall == pytest.approx(0)
    assert by_condition["full"].false_positive_rate == pytest.approx(0)

    variable = next(bug for bug in bugs if bug.operator == "variable_swap")
    variable_prompts = [
        prompt
        for prompt in client.prompts
        if f"Line {variable.absolute_line}:" in prompt or "build_record is under review" in prompt
    ]
    assert any("Developer intent:" in prompt and "models.py" in prompt for prompt in variable_prompts)
    assert any("Developer intent:" not in prompt and "models.py" not in prompt for prompt in variable_prompts)


def test_seed_command_lists_operators(tmp_path: Path, capsys):
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    repo = _corpus(tmp_path)
    with pytest.raises(SystemExit) as caught:
        main(["seed", "--repo", str(repo), "--max-per-class", "5"])
    assert caught.value.code == 0
    output = capsys.readouterr().out
    assert "variable_swap" in output
    assert "dict_key_swap" in output
    assert "loop_iterable_swap" in output
