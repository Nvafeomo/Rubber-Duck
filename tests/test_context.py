from pathlib import Path

from rubberduck.context import format_snippets, related_snippets
from rubberduck.models import Settings


def test_jedi_pulls_a_definition_from_another_file(tmp_path: Path):
    package = tmp_path / "samplelib"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "models.py").write_text(
        "def label(value):\n    return str(value)\n",
        encoding="utf-8",
    )
    source = (
        "from samplelib.models import label\n"
        "\n"
        "def greet():\n"
        "    return label('ada')\n"
    )
    app = package / "app.py"
    app.write_text(source, encoding="utf-8")

    snippets = related_snippets(
        source,
        app,
        changed={4},
        repo=tmp_path,
        settings=Settings(),
    )
    rendered = format_snippets(snippets)
    assert "models.py" in rendered
    assert "def label" in rendered


def test_same_file_definition_is_not_context(tmp_path: Path):
    source = "def label(value):\n    return value\n\ndef greet():\n    return label('ada')\n"
    app = tmp_path / "app.py"
    app.write_text(source, encoding="utf-8")
    snippets = related_snippets(source, app, changed={4}, repo=tmp_path, settings=Settings())
    assert snippets == []
