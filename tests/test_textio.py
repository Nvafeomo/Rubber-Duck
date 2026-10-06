from rubberduck.textio import without_bom


def test_leading_bom_is_removed_once():
    assert without_bom("\ufeffdef ready():\n    return 1\n") == "def ready():\n    return 1\n"
    assert without_bom("def ready():\n") == "def ready():\n"
