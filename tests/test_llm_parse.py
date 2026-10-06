import json

import pytest

from rubberduck.llm import ReviewError, parse_concerns


def test_parse_object_and_fence():
    payload = '```json\n{"concerns": [{"file": "a.py", "line": 4, "question": "key?"}]}\n```'
    concerns = parse_concerns(payload)
    assert len(concerns) == 1
    assert concerns[0].file == "a.py"
    assert concerns[0].line == 4
    assert concerns[0].question == "key?"


def test_drops_malformed_items_and_duplicates_and_stops_at_three():
    payload = json.dumps(
        {
            "concerns": [
                {"file": "a.py", "line": "2", "question": "first?"},
                {"file": "a.py", "line": "2", "question": "first?"},
                {"file": "a.py", "line": 0, "question": "nope"},
                {"file": "a.py", "question": "missing line"},
                {"file": "a.py", "line": 3, "question": "second?"},
                {"file": "a.py", "line": 4, "question": "third?"},
                {"file": "a.py", "line": 5, "question": "fourth?"},
            ]
        }
    )
    concerns = parse_concerns(payload)
    assert [(item.line, item.question) for item in concerns] == [
        (2, "first?"),
        (3, "second?"),
        (4, "third?"),
    ]


def test_rejects_non_json():
    with pytest.raises(ReviewError):
        parse_concerns("not json")
