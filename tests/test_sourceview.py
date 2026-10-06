from rubberduck.sourceview import select_view


def test_small_file_is_numbered_in_full():
    source = "def ready():\n    return 1\n"
    view = select_view(source, {2}, max_file_lines=400, max_scope_lines=200)
    assert view == "1| def ready():\n2|     return 1"


def test_large_file_keeps_the_function_and_its_line_numbers():
    prelude = "\n".join(f"value_{index} = {index}" for index in range(450))
    source = prelude + "\n\ndef total(items, other):\n    return len(items) + other\n"
    view = select_view(source, {453}, max_file_lines=400, max_scope_lines=200)
    assert "value_0 = 0" not in view
    assert "452| def total(items, other):" in view
    assert "453|     return len(items) + other" in view
