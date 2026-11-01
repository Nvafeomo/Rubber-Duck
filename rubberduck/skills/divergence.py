"""Code edits that make a skill quietly stop matching one of its claims.

Each edit keeps the code valid and ordinary-looking, so it is hard to spot
without reading the docs, and each is tied to the specific claim it breaks:

- sort_flip: a result sort runs the other way ("largest first" claims)
- recursive_glob: a folder search also walks every subfolder ("folder" claims)
- skip_large_files: a file loop silently skips big files ("every file" claims)
- changed_default: a number the docs state is changed in the code
- dropped_field: an output field the docs list is no longer written

Ties between edits and claims are checked with words, not meaning, so a person
should still read a sample of the seeded cases.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from rubberduck.skills.claims import Claim
from rubberduck.skills.loader import Skill

KINDS = ("sort_flip", "recursive_glob", "skip_large_files", "changed_default", "dropped_field")
_ORDER = re.compile(r"\b(descending|ascending|largest|smallest|highest|lowest|newest|oldest|sorted|ordered|ranked)\b", re.I)
_OUTPUT = re.compile(r"\b(output|outputs|returns?|report|json|fields?|includes?|contains?|columns?|keys?|entry|entries)\b", re.I)
_FOLDER = re.compile(r"\b(folder|directory|dir)\b", re.I)
_EVERY_FILE = re.compile(r"\b(every|all|each)\s+(\S+\s+){0,2}(files?|documents?|images?|pdfs?|pages?|sheets?|slides?|reports?)\b", re.I)
_FILE_ITER = re.compile(r"\b(r?glob|iterdir)\(")
_STOP = set("the a an and or of to in on for with by from as at is are be this that it its into your you use when "
            "what which will can may each every all any file files folder".split())


@dataclass(frozen=True)
class Edit:
    kind: str
    file: str
    line: int
    text: str  # full new file text
    claim: Claim
    what: str


def candidate_edits(skill: Skill, claims: list[Claim]) -> list[Edit]:
    edits: list[Edit] = []
    for script in skill.python_scripts:
        try:
            tree = ast.parse(script.text)
        except SyntaxError:
            continue
        lines = script.text.splitlines(keepends=True)
        parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for function in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            words = _function_words(function)
            for node in ast.walk(function):
                if isinstance(node, ast.Call):
                    edits += _sort_flip(node, script, lines, claims, words | _content_words(lines[node.lineno - 1]))
                    edits += _recursive_glob(node, script, lines, claims, words | _content_words(lines[node.lineno - 1]))
                if isinstance(node, ast.Dict) and _is_output_dict(node, parents):
                    edits += _dropped_field(node, script, lines, claims)
            edits += _skip_large_files(function, script, lines, claims, words)
            edits += _function_defaults(function, script, lines, claims)
        edits += _module_constants(tree, script, lines, claims)
    return [edit for edit in _dedupe(edits) if _compiles(edit)]


# -- operators -------------------------------------------------------------

def _sort_flip(node, script, lines, claims, words):
    func = node.func
    is_sort = (isinstance(func, ast.Name) and func.id == "sorted") or (isinstance(func, ast.Attribute) and func.attr == "sort")
    if not is_sort or node.lineno != node.end_lineno or not any(kw.arg in {"key", "reverse"} for kw in node.keywords):
        return []
    segment = ast.get_source_segment(script.text, node) or ""
    if re.search(r"glob|listdir|iterdir|scandir|walk", segment):
        return []
    claim = _related_claim(claims, _ORDER, words)
    if claim is None:
        return []
    line = lines[node.lineno - 1]
    if "reverse=True" in line:
        new = line.replace("reverse=True", "reverse=False", 1)
    elif "reverse=False" in line:
        new = line.replace("reverse=False", "reverse=True", 1)
    else:
        col = node.end_col_offset - 1
        new = line[:col] + ", reverse=True" + line[col:]
    return [_edit("sort_flip", script, lines, node.lineno, [new], claim, "the result order is reversed")]


def _recursive_glob(node, script, lines, claims, words):
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "glob") or (isinstance(func.value, ast.Name) and func.value.id == "glob"):
        return []
    # The claim must be about these files: it names a word from the glob pattern
    # (e.g. "xml" in "theme*.xml") or says every file in the folder.
    pattern = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) else ""
    pattern_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", pattern)}
    claim = next((c for c in claims if _FOLDER.search(c.text) and not re.search(r"skill'?s? (own )?(directory|folder)", c.text, re.I)
                  and (pattern_words & {w.lower() for w in re.findall(r"[A-Za-z]{3,}", c.text)} or _EVERY_FILE.search(c.text))
                  and _content_words(c.text) & words), None)
    if claim is None:
        return []
    line = lines[func.end_lineno - 1]
    col = func.end_col_offset - len("glob")
    new = line[:col] + "rglob" + line[col + len("glob"):]
    return [_edit("recursive_glob", script, lines, func.end_lineno, [new], claim,
                  "the folder search now also goes through every subfolder")]


def _skip_large_files(function, script, lines, claims, words):
    out = []
    for stmt in function.body:
        if not isinstance(stmt, ast.For) or not isinstance(stmt.target, ast.Name) or stmt.iter.lineno != stmt.iter.end_lineno:
            continue
        if not _FILE_ITER.search(ast.get_source_segment(script.text, stmt.iter) or ""):
            continue
        local = words | _content_words(lines[stmt.lineno - 1])
        claim = next((c for c in claims if _EVERY_FILE.search(c.text) and _content_words(c.text) & local), None)
        if claim is None:
            continue
        first = stmt.body[0]
        indent = " " * first.col_offset
        name = stmt.target.id
        block = [f"{indent}if {name}.stat().st_size > 5_000_000:\n", f"{indent}    continue\n"]
        out.append(_insert("skip_large_files", script, lines, first.lineno, block, claim,
                           "files over 5 MB are silently skipped"))
    return out


def _function_defaults(function, script, lines, claims):
    out = []
    args = function.args
    positional = [*args.posonlyargs, *args.args]
    pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
    pairs += [(arg, d) for arg, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
    for arg, default in pairs:
        edit = _number_edit(default, script, lines, claims, arg.arg)
        if edit:
            out.append(edit)
    return out


def _module_constants(tree, script, lines, claims):
    out = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) \
                and stmt.targets[0].id.isupper():
            edit = _number_edit(stmt.value, script, lines, claims, stmt.targets[0].id)
            if edit:
                out.append(edit)
    return out


def _number_edit(node, script, lines, claims, name: str):
    if not (isinstance(node, ast.Constant) and type(node.value) in (int, float)) or node.value in (0, 1, -1):
        return None
    if node.lineno != node.end_lineno:
        return None
    text = lines[node.lineno - 1][node.col_offset:node.end_col_offset]
    plain = text.replace("_", "")
    name_words = _content_words(name) | {w for w in re.split(r"_+", name.lower()) if len(w) >= 3}
    claim = next((c for c in claims if re.search(rf"(?<![\d.x]){re.escape(plain)}(?![\d.x])", c.text.replace(",", ""))
                  and _content_words(c.text) & name_words), None)
    if claim is None:
        return None
    value = node.value * 2
    new_text = str(int(value)) if isinstance(node.value, int) else repr(float(value))
    line = lines[node.lineno - 1]
    new = line[:node.col_offset] + new_text + line[node.end_col_offset:]
    return _edit("changed_default", script, lines, node.lineno, [new], claim,
                 f"the value {text} that the docs state is now {new_text}")


def _dropped_field(node, script, lines, claims):
    keys = [k for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
    if len(keys) < 3 or len(keys) != len(node.keys):
        return []
    out = []
    for index, key in enumerate(node.keys):
        claim = _claim_naming_key(claims, key.value)
        if claim is None:
            continue
        value = node.values[index]
        if key.lineno != value.end_lineno:
            continue
        own_line = lines[key.lineno - 1].strip()
        segment = lines[key.lineno - 1][key.col_offset:value.end_col_offset]
        if own_line.rstrip(",") == segment.strip():
            new_lines = lines[: key.lineno - 1] + lines[key.lineno:]
            target_line = max(key.lineno - 1, node.lineno)
        else:
            line = lines[key.lineno - 1]
            end = value.end_col_offset
            rest = line[end:]
            if rest.lstrip().startswith(","):
                end += len(rest) - len(rest.lstrip()) + 1
                end += len(line[end:]) - len(line[end:].lstrip(" "))
                start = key.col_offset
            elif index > 0:
                prev = node.values[index - 1]
                if prev.end_lineno != key.lineno:
                    continue
                start = prev.end_col_offset
            else:
                continue
            new_lines = [*lines]
            new_lines[key.lineno - 1] = line[:start] + line[end:]
            target_line = key.lineno
        out.append(Edit(kind="dropped_field", file=script.relpath, line=target_line, text="".join(new_lines),
                        claim=claim, what=f'the "{key.value}" field the docs describe is no longer written'))
    return out


# -- helpers ---------------------------------------------------------------

def _edit(kind, script, lines, line_no, replacement, claim, what) -> Edit:
    new_lines = lines[: line_no - 1] + replacement + lines[line_no:]
    return Edit(kind=kind, file=script.relpath, line=line_no, text="".join(new_lines), claim=claim, what=what)


def _insert(kind, script, lines, before_line, block, claim, what) -> Edit:
    new_lines = lines[: before_line - 1] + block + lines[before_line - 1:]
    return Edit(kind=kind, file=script.relpath, line=before_line, text="".join(new_lines), claim=claim, what=what)


def _related_claim(claims, pattern, words):
    """A claim that has the trigger word and shares a word with the function or the edited line."""
    for claim in claims:
        if not pattern.search(claim.text):
            continue
        claim_words = _content_words(claim.text)
        if claim_words & words:
            return claim
    return None


def _claim_naming_key(claims, key: str):
    """A claim about output that names this key, quoted or as its words."""
    parts = [p for p in re.split(r"[_\W]+", key.lower()) if p]
    if not parts or (len(parts) == 1 and len(parts[0]) < 4):
        return None
    for claim in claims:
        text = claim.text.lower()
        quoted = f"`{key.lower()}`" in text or f'"{key.lower()}"' in text
        worded = len(parts) > 1 and all(re.search(rf"\b{re.escape(p)}", text) for p in parts)
        if (quoted or worded) and _OUTPUT.search(claim.text):
            return claim
    return None


def _is_output_dict(node, parents) -> bool:
    """A dict that is returned, dumped to JSON, or written out."""
    parent = parents.get(id(node))
    if isinstance(parent, ast.Return):
        return True
    if isinstance(parent, ast.Call):
        name = ast.unparse(parent.func)
        return bool(re.search(r"json\.dumps?|write|append|jsonify|DataFrame", name))
    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
        targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
        return any(re.search(r"result|report|output|summary|entry|record|row|payload", ast.unparse(t), re.I) for t in targets)
    if isinstance(parent, ast.List):
        return _is_output_dict(parent, parents)
    return False


def _function_words(function) -> set[str]:
    """Name, docstring, and argument names: what the function is about, not every word in it."""
    parts = [function.name, ast.get_docstring(function) or ""]
    parts += [arg.arg for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]]
    return _content_words(" ".join(parts))


def _content_words(text: str) -> set[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower().replace("_", " ")
    return {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", text) if w not in _STOP}


def _dedupe(edits: list[Edit]) -> list[Edit]:
    seen = set()
    out = []
    for edit in edits:
        key = (edit.kind, edit.file, edit.line)
        if key not in seen:
            seen.add(key)
            out.append(edit)
    return out


def _compiles(edit: Edit) -> bool:
    try:
        compile(edit.text, edit.file, "exec")
        return True
    except SyntaxError:
        return False
