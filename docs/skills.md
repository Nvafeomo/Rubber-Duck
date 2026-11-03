# Skill Audits (ICSE 2027 Industry Challenge 3)

This branch extends RubberDuck to check **agent skills** for intent-behavior
misalignment: places where what a skill says it does (SKILL.md, README, other
docs) and what its code does are not the same.

## How it works

`rubberduck skills audit <skill folder>`:

1. **Load** the skill: docs, scripts (Python, shell, JS), config files, and
   fenced code blocks in SKILL.md and the README.
2. **Extract claims** from the docs: the frontmatter description, list items,
   and sentences, each with its file and line (`claims.py`).
3. **Collect static facts** from the code (`behaviors.py`):
   - behaviors that matter for trust (network, env vars, credentials, file
     writes and deletes, processes, dynamic code, persistence), each with a
     file, line, and function;
   - call chains that follow calls across the skill's own files;
   - composite flows, where a source (secrets, system info) and a sink
     (network, process) are reachable from the same entry point. A flow is
     marked "dataflow" when the secret-derived value actually reaches the
     sink, including through functions in other files that return it;
   - config files are scanned for endpoints and hardcoded secrets.
4. **One model call** gets the claims, the numbered docs and code, and the
   static facts. It first groups related claims into intent units (what the
   skill promises, and whether and where the code does it), then returns
   findings: type, location, evidence, call chain, risk, and explanation
   (`audit.py`).

The three finding types are the challenge's:

| Type | Meaning |
|---|---|
| `unimplemented_intent` | The docs promise something the code never does |
| `undeclared_behavior` | The code does something the docs never mention |
| `divergent_behavior` | The code does something related to a claim, but differently |

## Commands

```
rubberduck skills facts PATH            # claims + static facts, no model call
rubberduck skills audit PATH --dry-run  # show the prompt
rubberduck skills audit PATH            # run the audit (needs GEMINI_API_KEY)
rubberduck skills collect URL_OR_FOLDER # copy skills into benchmark/ as drafts
rubberduck skills status                # count cases and check labels
rubberduck skills seed                  # plant misalignments in aligned cases
rubberduck skills suggest-divergence ID # model drafts divergent edits for you to review
rubberduck skills eval --pause 4 --yes  # run every method and score it
```

## Building the benchmark (your part)

### 1. Collect skills

Pick public repos that contain skills (folders with a `SKILL.md`) and run:

```
rubberduck skills collect https://github.com/OWNER/REPO
```

Each skill with at least one Python script becomes a draft case in
`benchmark/cases/<id>/` with a copy of the skill and a `label.json`.
`--all-languages` also keeps shell and JS-only skills.

Aim for 40 to 60 skills from several repos. Check each repo's license allows
copying before you commit the skills. If it doesn't, keep the repo URL and
commit hash in the label and leave the copy out of git.

### 2. Label each skill

Open `label.json`. The `suggestions` section lists the claims, risky
behaviors, and composite flows the tool found. **These are hints, not
answers.** Read the docs and the code yourself and decide.

- If the skill does what its docs say: set `"aligned": true`.
- If it doesn't: set `"aligned": false` and add one entry per problem:

```json
"misalignments": [
  {
    "type": "undeclared_behavior",
    "file": "scripts/upload.py",
    "lines": [42],
    "claim": "",
    "note": "posts the file to an analytics server; docs only say it converts files",
    "related": ["scripts/util.py:10"]
  }
]
```

  - `lines`: where the problem happens. For `unimplemented_intent`, use the
    doc file and the line of the claim.
  - `related` (optional): other `file:line` spots that also count as correct.

The challenge also asks the benchmark to record declared intents and real
behaviors. Fill these for each verified skill (the `suggestions` section is a
starting point). They are not scored, but they make the benchmark useful to
other people and back up your labels:

```json
"intents": [{"summary": "converts CSV to JSON", "source": "SKILL.md:3",
             "implemented_at": ["scripts/convert.py:10"], "expected_result": "a .json file next to the input"}],
"behaviors": [{"category": "network", "location": "scripts/helpers.py:8", "declared": false}]
```

Then set `"status": "verified"`. Only verified cases are scored.

Rules of thumb:
- Writing the output file the docs describe is not undeclared.
- A helper that reads an API key the docs tell you to set is not undeclared.
- Keep a short note for every decision. You'll need them for the paper and
  for a second labeler if you get one.

`rubberduck skills status` checks every verified label and prints any problems.

### 3. Seed extra cases

```
rubberduck skills seed
```

For every verified **aligned** real skill, this writes new cases with one
planted problem each, labeled automatically:

| Variant | What gets planted |
|---|---|
| `undeclared_env_network` | Reads `GITHUB_TOKEN` and sends it to a URL in the same function |
| `undeclared_cross_file` | A new helper file collects secret-looking env vars; the main script sends them |
| `undeclared_process` | Silently changes the global git credential setting |
| `unimplemented_claim` | Adds a claim to SKILL.md that no code backs up |
| `divergent_doc_swap` | Changes a detail in a claim (JSON to YAML, ascending to descending) |
| `divergent_code_semantic` | Changes the code so it contradicts a specific claim but still runs and looks normal: a stated number changes, a listed output field is dropped, a result sort flips, a folder search goes into subfolders, or big files are skipped. Only applied when the claim names the same value, field, or files |

`bug_code_mutation` (RubberDuck's original wrong-variable/key/loop seeding) is
still available with `--variants bug_code_mutation`, but it is not seeded by
default. Those bugs break the code on their own, so a model can catch them
without reading the docs, and they are bugs rather than doc-code divergence.

Template edits are strict on purpose, so many skills get none. Report them as
"template-seeded" and keep them a small part of the results.

### 3b. Hand-made divergences (the main seeded set)

The most convincing seeded cases are ones you write: pick a clean skill, read
one claim, and change the code so it quietly stops matching it (a different
default, output path, field, filter, unit, or format) while still running and
looking normal. Aim for 10 to 15. Save each as a new case folder with a label
like the seeded ones, with `"origin": "seeded"` and `"variant": "hand_divergence"`.

To get started faster, have a model draft candidates:

```
rubberduck skills suggest-divergence <case_id> --model <a different model>
```

Each valid draft becomes `benchmark/cases/<case_id>__assisted_<n>/` with
status `draft`. Its `label.json` shows the original line and the new code under
`review`. Keep it only if the edit really contradicts the claim and looks like
ordinary code; edit the code or note if needed, then set `"status": "verified"`.
Drafts that add network calls, processes, or env reads are rejected
automatically, because those are undeclared behavior, not divergence.

Use a different model for drafting than the one you audit with, so the same
model is not writing and grading its own test, and say so in the paper.

### 4. Run the evaluation

```
rubberduck skills eval --pause 4 --yes
```

Methods compared:

| Method | What it is |
|---|---|
| `full` | RubberDuck: docs + code + static facts |
| `no_facts` | Same call without static facts (ablation) |
| `single_file` | Docs + only the main script, no facts (ablation) |
| `static` | What a marketplace scanner does: every medium/high risk behavior is reported, docs ignored |
| `rules` | Static analysis + keyword matching, no model |
| `similarity` | TF-IDF similarity between claims and code, no model |

A finding counts as correct when its type matches a label and it points within
3 lines of it (directly, through its evidence, or through the claim it cites).
Results go to `results/skills/`:

- `skills-eval.csv`: one row per case and method
- `skills-eval-summary.csv`: precision, recall, F1, false alarms on aligned
  skills, recall per type, latency, tokens
- `skills-eval-by-variant.csv`: recall per seeded variant
- `findings/`: every method's raw findings, for reading the mistakes

Report real and seeded cases separately in the paper. Seeded cases are easier
to label but less realistic.

## Limits worth stating in the paper

- The static scan is precise for Python and pattern-based for shell and JS.
- Call chains follow the skill's own functions and imports, not third-party code.
- Data flow is only tracked inside one function; across functions the tool
  reports reachability, not proof that data moves.
- Large skills are trimmed to fit a line budget per file and per prompt.
