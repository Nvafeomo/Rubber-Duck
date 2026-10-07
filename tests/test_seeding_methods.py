from pathlib import Path

from rubberduck.evaluate import discover_bugs

_SOURCE = '''
class Gradebook:
    def report(self, students, tutoring):
        """Average every student's exam scores."""
        totals = {}
        for name in students:
            record = {"exams": 90, "homework": 70}
            totals[name] = record["exams"]
        return totals
'''


def test_methods_inside_classes_are_seeded(tmp_path: Path):
    (tmp_path / "gradebook.py").write_text(_SOURCE, encoding="utf-8")

    bugs = discover_bugs(tmp_path, max_per_class=5, seed=0, include_tests=False)

    assert {bug.operator for bug in bugs} == {"variable_swap", "dict_key_swap", "loop_iterable_swap"}
    for bug in bugs:
        compile(bug.mutated_source, "gradebook.py", "exec")
        original = bug.file_source.splitlines()
        mutated = bug.mutated_source.splitlines()
        changed = [i + 1 for i, (a, b) in enumerate(zip(original, mutated)) if a != b]
        assert changed == [bug.absolute_line]
