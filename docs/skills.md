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
     (network, process) are reachable from the same entry point.
4. **One model call** gets the claims, the numbered docs and code, and the
   static facts, and returns findings: type, location, evidence, call chain,
   risk, and explanation (`audit.py`).

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
| `divergent_code_mutation` | RubberDuck's original bug seeding (wrong variable, key, or loop) |

The planted network code points at a `.invalid` domain, which can never
resolve, so nothing is ever sent.

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
