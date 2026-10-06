import shutil
import subprocess
from pathlib import Path

import pytest

from rubberduck.llm import Completion, Usage
from rubberduck.models import Concern, Settings
from rubberduck.review import run_review


class ScriptedReviewer:
    def __init__(self, concerns):
        self.concerns = concerns
        self.prompts = []

    def complete(self, prompt: str) -> Completion:
        self.prompts.append(prompt)
        return Completion(list(self.concerns), Usage(0.0, 1, 1))


def _git_repo(tmp_path: Path) -> Path:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH")
    subprocess.run([git, "init"], cwd=tmp_path, check=True, capture_output=True)
    app = tmp_path / "app.py"
    app.write_text(
        "def total(items, other):\n    return items[0] + other\n",
        encoding="utf-8",
    )
    subprocess.run([git, "add", "app.py"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_concern_blocks_until_forced(tmp_path: Path, capsys):
    repo = _git_repo(tmp_path)
    reviewer = ScriptedReviewer([Concern("app.py", 2, "Did you mean other?")])
    blocked = run_review(
        repo,
        intent="sum the items",
        force=False,
        interactive=False,
        dry_run=False,
        client=reviewer,
        settings=Settings(),
        pass_on_error=False,
    )
    assert blocked == 1
    assert "Did you mean other?" in capsys.readouterr().out

    allowed = run_review(
        repo,
        intent="sum the items",
        force=True,
        interactive=False,
        dry_run=False,
        client=reviewer,
        settings=Settings(),
        pass_on_error=False,
    )
    assert allowed == 0
    assert "allowing the commit" in capsys.readouterr().out


def test_clean_review_passes(tmp_path: Path, capsys):
    repo = _git_repo(tmp_path)
    code = run_review(
        repo,
        intent="sum the items",
        force=False,
        interactive=False,
        dry_run=False,
        client=ScriptedReviewer([]),
        settings=Settings(),
        pass_on_error=False,
    )
    assert code == 0
    assert "no concerns" in capsys.readouterr().out


def test_dry_run_prints_intent_without_calling_the_model(tmp_path: Path, capsys):
    repo = _git_repo(tmp_path)
    code = run_review(
        repo,
        intent="sum the items",
        force=False,
        interactive=False,
        dry_run=True,
        client=None,
        settings=Settings(),
        pass_on_error=False,
    )
    captured = capsys.readouterr().out
    assert code == 0
    assert "sum the items" in captured
    assert "return items[0] + other" in captured
    assert "2|" in captured
