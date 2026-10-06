from rubberduck.prompt import build_prompt


def test_full_prompt_includes_intent_and_context():
    prompt = build_prompt(
        relpath="app.py",
        diff="Line 3:\n- old\n+ new",
        numbered_source="3| new",
        focus="3",
        intent="save the record",
        context="# models.py:1\n1| def label(value):",
    )
    assert "File: app.py" in prompt
    assert "Developer intent:\nsave the record" in prompt
    assert "Related definitions from other files:" in prompt
    assert "3| new" in prompt
    assert "cite these line numbers" in prompt


def test_ablations_drop_the_sections_they_exclude():
    code_only = build_prompt(
        relpath="app.py",
        diff="(no textual diff)",
        numbered_source="1| x = 1",
        focus="1",
        intent=None,
        context=None,
    )
    assert "Developer intent:" not in code_only
    assert "Related definitions" not in code_only

    empty_intent = build_prompt(
        relpath="app.py",
        diff="diff",
        numbered_source="1| x = 1",
        focus="1",
        intent="",
        context=None,
    )
    assert "(none given)" in empty_intent
