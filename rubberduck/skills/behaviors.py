"""Static facts about what a skill's code does.

Three things come out of this module:

* behaviors: calls and accesses that matter for trust (network, environment
  variables, credentials, files, processes, dynamic code), each with a file,
  line, and enclosing function;
* call chains: how each behavior is reached from a script's entry point,
  following calls across the skill's own files;
* composite flows: a source (secrets, files, system info) and a sink (network,
  process) reachable from the same entry point. Each piece can look harmless
  alone; together they can move data out of the machine.

Python is analysed with ``ast``. Shell and JavaScript files and inline code
blocks in the docs get a line-based pattern scan, which is coarser but keeps
them from being invisible.
"""

from __future__ import annotations

import ast
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from rubberduck.skills.loader import Skill

SOURCE_CATEGORIES = {"env_read", "credential_access", "file_read", "system_info", "clipboard"}
SINK_CATEGORIES = {"network", "process"}

# (category, qualified-name prefixes). A prefix ending in "." matches anything under it.
_CALL_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("network", ("requests.", "httpx.", "urllib.request.", "urllib3.", "http.client.", "socket.socket",
                 "socket.create_connection", "aiohttp.", "smtplib.", "ftplib.", "paramiko.", "websocket.",
                 "websockets.", "telnetlib.", "xmlrpc.client.")),
    ("process", ("subprocess.", "os.system", "os.popen", "os.exec*", "os.spawn*", "pty.spawn", "asyncio.create_subprocess*")),
    ("dynamic_code", ("eval", "exec", "compile", "__import__", "importlib.import_module", "marshal.loads",
                      "pickle.loads", "pickle.load", "runpy.")),
    ("env_read", ("os.getenv", "os.environ", "dotenv.")),
    ("file_delete", ("os.remove", "os.unlink", "os.rmdir", "shutil.rmtree", "os.removedirs")),
    ("file_write", ("shutil.copy*", "shutil.move", "os.rename", "os.replace", "shutil.make_archive", "zipfile.ZipFile",
                    "tarfile.open")),
    ("file_read", ("glob.glob", "glob.iglob", "os.walk", "os.listdir", "os.scandir")),
    ("encoding", ("base64.", "zlib.compress", "zlib.decompress", "binascii.", "codecs.encode", "codecs.decode")),
    ("system_info", ("platform.", "getpass.getuser", "socket.gethostname", "uuid.getnode", "os.uname", "os.getlogin")),
    ("clipboard", ("pyperclip.", "tkinter.Tk.clipboard_get")),
]
_METHOD_RULES = {
    "write_text": "file_write", "write_bytes": "file_write", "unlink": "file_delete", "rmdir": "file_delete",
    "read_text": "file_read", "read_bytes": "file_read", "rglob": "file_read", "iterdir": "file_read",
}
_SENSITIVE_STRING = re.compile(
    r"(\.ssh\b|id_rsa|id_ed25519|\.aws[/\\]credentials|\.netrc|\.git-credentials|\.npmrc|\.pypirc|keychain|"
    r"Login Data|Cookies\b|wallet\.dat|\.docker[/\\]config\.json|\.kube[/\\]config|/etc/passwd|/etc/shadow)",
    re.IGNORECASE,
)
_PERSISTENCE_STRING = re.compile(r"(crontab|\.bashrc|\.zshrc|\.bash_profile|\.profile\b|LaunchAgents|systemd|autostart)", re.IGNORECASE)
_LINE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("network", re.compile(r"\b(curl|wget|nc|ncat|scp|rsync|ssh|ftp)\s|\bfetch\(|\baxios\b|\bhttps?\.request\(|XMLHttpRequest|new WebSocket")),
    ("process", re.compile(r"child_process|\bexecSync\(|\bspawn\(|\bbash -c\b|\|\s*(ba)?sh\b")),
    ("dynamic_code", re.compile(r"\beval\s*\(|\beval\s+\$|new Function\(")),
    ("env_read", re.compile(r"process\.env|\$\{?[A-Z_]*(KEY|TOKEN|SECRET|PASS|PASSWORD|AWS|GITHUB)[A-Z_]*\}?")),
    ("file_delete", re.compile(r"\brm\s+-[a-z]*r|fs\.(unlink|rm|rmdir)")),
    ("file_write", re.compile(r"fs\.(writeFile|appendFile)|(^|\s)>>?\s*[~/$]")),
    ("encoding", re.compile(r"\bbase64\b|\batob\(|\bbtoa\(")),
    ("credential_access", _SENSITIVE_STRING),
    ("persistence", _PERSISTENCE_STRING),
]
_RISK = {
    "network": "high", "process": "high", "dynamic_code": "high", "credential_access": "high", "persistence": "high",
    "file_delete": "medium", "env_read": "medium", "clipboard": "medium", "encoding": "low", "file_write": "low",
    "system_info": "low", "file_read": "low",
}


_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Behavior:
    category: str
    api: str
    file: str
    line: int
    function: str
    snippet: str

    @property
    def node(self) -> str:
        return f"{self.file}::{self.function}"

    @property
    def risk(self) -> str:
        return _RISK.get(self.category, "low")


@dataclass(frozen=True)
class CompositeFlow:
    source: Behavior
    sink: Behavior
    entry: str
    evidence: str  # "dataflow" (same function, value reaches the sink) or "reachable"


@dataclass
class StaticFacts:
    behaviors: list[Behavior] = field(default_factory=list)
    chains: dict[int, list[str]] = field(default_factory=dict)
    flows: list[CompositeFlow] = field(default_factory=list)
    functions: dict[str, list[str]] = field(default_factory=dict)  # file -> ["name (line): first docstring line"]
    parse_errors: list[str] = field(default_factory=list)

    def categories(self) -> set[str]:
        return {item.category for item in self.behaviors}


def analyze_skill(skill: Skill) -> StaticFacts:
    facts = StaticFacts()
    graph: dict[str, set[str]] = {}
    entries: list[str] = []
    local_modules = _local_modules(skill)
    tainted_sinks: set[tuple[str, int]] = set()

    for script in skill.scripts:
        if script.language == "python":
            try:
                tree = ast.parse(script.text)
            except SyntaxError as exc:
                facts.parse_errors.append(f"{script.relpath}: {exc.msg} (line {exc.lineno})")
                facts.behaviors.extend(_scan_lines(script.text, script.relpath, 0))
                continue
            visitor = _PythonVisitor(script.relpath, script.text, local_modules)
            visitor.visit(tree)
            facts.behaviors.extend(visitor.behaviors)
            facts.functions[script.relpath] = visitor.function_summaries
            for caller, callees in visitor.calls.items():
                graph.setdefault(caller, set()).update(callees)
            entries.append(f"{script.relpath}::<module>")
            tainted_sinks.update(visitor.tainted_sinks)
        else:
            facts.behaviors.extend(_scan_lines(script.text, script.relpath, 0))
            entries.append(f"{script.relpath}::<module>")

    for block in skill.inline_code:
        if block.language in {"python", "py"}:
            try:
                tree = ast.parse(block.text)
            except SyntaxError:
                facts.behaviors.extend(_scan_lines(block.text, block.doc, block.start_line - 1, function="<inline>"))
                continue
            visitor = _PythonVisitor(block.doc, block.text, local_modules, line_offset=block.start_line - 1, module_name="<inline>")
            visitor.visit(tree)
            facts.behaviors.extend(visitor.behaviors)
            for caller, callees in visitor.calls.items():
                graph.setdefault(caller, set()).update(callees)
            entries.append(f"{block.doc}::<inline>")
        else:
            facts.behaviors.extend(_scan_lines(block.text, block.doc, block.start_line - 1, function="<inline>"))

    facts.behaviors = _dedupe(facts.behaviors)
    paths = {entry: _shortest_paths(graph, entry) for entry in entries}
    for index, behavior in enumerate(facts.behaviors):
        best: list[str] | None = None
        for entry_paths in paths.values():
            chain = entry_paths.get(behavior.node)
            if chain is not None and (best is None or len(chain) < len(best)):
                best = chain
        facts.chains[index] = best or [behavior.node]

    facts.flows = _composite_flows(facts.behaviors, paths, tainted_sinks)
    return facts


def format_facts(facts: StaticFacts, max_behaviors: int = 40, max_flows: int = 10, max_functions: int = 60) -> str:
    lines: list[str] = []
    if facts.behaviors:
        lines.append("Observed behaviors, riskiest first (category | location | function | code):")
        order = sorted(range(len(facts.behaviors)),
                       key=lambda i: (_RANK[facts.behaviors[i].risk], facts.behaviors[i].file, facts.behaviors[i].line))
        for index in order[:max_behaviors]:
            behavior = facts.behaviors[index]
            chain = facts.chains.get(index, [])
            via = f" | reached via {' -> '.join(_short(node) for node in chain)}" if len(chain) > 1 else ""
            lines.append(f"- [B{index + 1}] {behavior.category} ({behavior.risk}) | {behavior.file}:{behavior.line} | "
                         f"{behavior.function} | {behavior.snippet}{via}")
        if len(facts.behaviors) > max_behaviors:
            lines.append(f"- ... {len(facts.behaviors) - max_behaviors} more not shown")
    else:
        lines.append("Observed behaviors: none of the tracked kinds (network, processes, env vars, credentials, file changes, dynamic code).")
    if facts.flows:
        lines.append("Composite flows (a data source and a sink reachable from the same entry point):")
        for flow in facts.flows[:max_flows]:
            lines.append(f"- {flow.source.category} at {flow.source.file}:{flow.source.line} -> {flow.sink.category} at "
                         f"{flow.sink.file}:{flow.sink.line} (entry {_short(flow.entry)}, {flow.evidence})")
    if facts.functions:
        lines.append("Functions defined in the scripts:")
        listed = [f"- {file}: {item}" for file, items in facts.functions.items() for item in items]
        lines.extend(listed[:max_functions])
        if len(listed) > max_functions:
            lines.append(f"- ... {len(listed) - max_functions} more not shown")
    if facts.parse_errors:
        lines.append("Files that did not parse (pattern scan only): " + "; ".join(facts.parse_errors))
    return "\n".join(lines)


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, relpath: str, source: str, local_modules: dict[str, str], line_offset: int = 0,
                 module_name: str = "<module>") -> None:
        self.relpath = relpath
        self.lines = source.splitlines()
        self.local_modules = local_modules
        self.offset = line_offset
        self.module_name = module_name
        self.aliases: dict[str, str] = {}
        self.local_defs: set[str] = set()
        self.scope: list[str] = []
        self.behaviors: list[Behavior] = []
        self.calls: dict[str, set[str]] = {}
        self.function_summaries: list[str] = []
        self.tainted_sinks: set[tuple[str, int]] = set()
        self._taint: list[set[str]] = [set()]
        self._docstrings: set[int] = set()

    # -- scope ---------------------------------------------------------
    @property
    def current(self) -> str:
        return ".".join(self.scope) if self.scope else self.module_name

    @property
    def node_id(self) -> str:
        return f"{self.relpath}::{self.current}"

    def visit_Module(self, node: ast.Module) -> None:
        for item in ast.walk(node):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                if not isinstance(item, ast.Module):
                    self.local_defs.add(item.name)
                body = getattr(item, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    self._docstrings.add(id(body[0].value))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        doc = ast.get_docstring(node) or ""
        first = doc.strip().splitlines()[0] if doc.strip() else ""
        label = f"{self.current} (line {node.lineno + self.offset})" + (f": {first}" if first else "")
        self.function_summaries.append(label)
        self.calls.setdefault(self.node_id, set())
        self._taint.append(set())
        self.generic_visit(node)
        self._taint.pop()
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    # -- imports -------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            target = alias.name if alias.asname else alias.name.split(".")[0]
            self.aliases[local] = self._local_or(target)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            qualified = f"{module}.{alias.name}" if module else alias.name
            local_file = self.local_modules.get(module.split(".")[-1]) if module else None
            if local_file:
                self.aliases[local] = f"@{local_file}::{alias.name}"
            else:
                self.aliases[local] = qualified

    def _local_or(self, module: str) -> str:
        local_file = self.local_modules.get(module.split(".")[-1])
        return f"@{local_file}" if local_file else module

    # -- assignments (for simple taint) ---------------------------------
    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        if self._is_source_expr(node.value) or self._uses_taint(node.value):
            for target in node.targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        self._taint[-1].add(name.id)

    def _is_source_expr(self, expr: ast.AST) -> bool:
        for item in ast.walk(expr):
            if isinstance(item, (ast.Call, ast.Attribute, ast.Subscript)):
                category = self._category_for_expr(item)
                if category in SOURCE_CATEGORIES:
                    return True
            if isinstance(item, ast.Constant) and isinstance(item.value, str) and _SENSITIVE_STRING.search(item.value):
                return True
        return False

    def _uses_taint(self, expr: ast.AST) -> bool:
        names = self._taint[-1]
        return any(isinstance(item, ast.Name) and item.id in names for item in ast.walk(expr))

    # -- behaviors -----------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        name = self._resolve(node.func)
        category = self._category_for_call(node, name)
        if category:
            self._record(category, name or _attr_name(node.func), node.lineno)
            if category in SINK_CATEGORIES and any(self._uses_taint(arg) for arg in [*node.args, *[kw.value for kw in node.keywords]]):
                self.tainted_sinks.add((self.relpath, node.lineno + self.offset))
        self._record_call_edge(node.func, name)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._resolve(node.value) == "os.environ":
            self._record("env_read", "os.environ[...]", node.lineno)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self._resolve(node) == "os.environ":
            self._record("env_read", "os.environ", node.lineno)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and id(node) not in self._docstrings:
            if _SENSITIVE_STRING.search(node.value):
                self._record("credential_access", f"path {node.value[:60]!r}", node.lineno)
            elif _PERSISTENCE_STRING.search(node.value):
                self._record("persistence", f"path {node.value[:60]!r}", node.lineno)

    def _category_for_call(self, node: ast.Call, name: str | None) -> str | None:
        if name in {"open", "io.open", "builtins.open"}:
            mode = _open_mode(node)
            return "file_write" if any(flag in mode for flag in "wax+") else "file_read"
        if name:
            category = _match_rules(name)
            if category:
                return category
        if isinstance(node.func, ast.Attribute) and node.func.attr in _METHOD_RULES:
            return _METHOD_RULES[node.func.attr]
        return None

    def _category_for_expr(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Call):
            return self._category_for_call(node, self._resolve(node.func))
        if isinstance(node, ast.Subscript) and self._resolve(node.value) == "os.environ":
            return "env_read"
        if isinstance(node, ast.Attribute):
            name = self._resolve(node)
            return _match_rules(name) if name else None
        return None

    def _record(self, category: str, api: str, line: int) -> None:
        absolute = line + self.offset
        snippet = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.behaviors.append(Behavior(category=category, api=api, file=self.relpath, line=absolute,
                                       function=self.current, snippet=snippet[:120]))

    def _record_call_edge(self, func: ast.AST, name: str | None) -> None:
        caller = self.node_id
        self.calls.setdefault(caller, set())
        if name and name.startswith("@"):
            target = name[1:]
            if "::" not in target:
                return
            self.calls[caller].add(target)
            return
        if isinstance(func, ast.Name) and func.id in self.local_defs:
            self.calls[caller].add(f"{self.relpath}::{func.id}")
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in {"self", "cls"}:
            owner = self.scope[0] if self.scope else ""
            if owner:
                self.calls[caller].add(f"{self.relpath}::{owner}.{func.attr}")

    def _resolve(self, node: ast.AST) -> str | None:
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Call):
            inner = self._resolve(current.func)
            if inner is None:
                return None
            parts.append(inner)
            return ".".join(reversed(parts))
        if not isinstance(current, ast.Name):
            return None
        base = self.aliases.get(current.id, current.id)
        if base.startswith("@") and parts:
            # module.func on a local module -> @file::func
            file = base[1:].split("::")[0]
            return f"@{file}::{'.'.join(reversed(parts))}"
        parts.append(base)
        return ".".join(reversed(parts))


def _match_rules(name: str) -> str | None:
    """Rules: "pkg." matches the package and anything in it, "name*" is a plain
    prefix, and anything else matches the exact name or an attribute of it."""
    for category, prefixes in _CALL_RULES:
        for prefix in prefixes:
            if prefix.endswith("."):
                matched = name.startswith(prefix) or name == prefix[:-1]
            elif prefix.endswith("*"):
                matched = name.startswith(prefix[:-1])
            else:
                matched = name == prefix or name.startswith(prefix + ".")
            if matched:
                return category
    return None


def _open_mode(node: ast.Call) -> str:
    mode_node = node.args[1] if len(node.args) > 1 else next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return mode_node.value
    return "r"


def _attr_name(func: ast.AST) -> str:
    if isinstance(func, ast.Attribute):
        return f"*.{func.attr}"
    if isinstance(func, ast.Name):
        return func.id
    return "<call>"


def _scan_lines(text: str, relpath: str, offset: int, function: str = "<module>") -> list[Behavior]:
    found: list[Behavior] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        for category, pattern in _LINE_RULES:
            match = pattern.search(raw)
            if match:
                found.append(Behavior(category=category, api=match.group(0).strip()[:40], file=relpath,
                                      line=number + offset, function=function, snippet=stripped[:120]))
    return found


def _local_modules(skill: Skill) -> dict[str, str]:
    modules: dict[str, str] = {}
    for script in skill.python_scripts:
        path = PurePosixPath(script.relpath)
        name = path.stem if path.stem != "__init__" else path.parent.name
        modules.setdefault(name, script.relpath)
    return modules


def _dedupe(items: list[Behavior]) -> list[Behavior]:
    seen: set[tuple[str, str, int]] = set()
    out: list[Behavior] = []
    for item in items:
        key = (item.category, item.file, item.line)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=lambda item: (item.file, item.line, item.category))
    return out


def _shortest_paths(graph: dict[str, set[str]], start: str) -> dict[str, list[str]]:
    paths = {start: [start]}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in sorted(graph.get(node, ())):
            if nxt not in paths:
                paths[nxt] = [*paths[node], nxt]
                queue.append(nxt)
    return paths


def _composite_flows(behaviors: list[Behavior], paths: dict[str, dict[str, list[str]]],
                     tainted_sinks: set[tuple[str, int]]) -> list[CompositeFlow]:
    flows: list[CompositeFlow] = []
    seen: set[tuple[int, int]] = set()
    sources = [(i, b) for i, b in enumerate(behaviors) if b.category in SOURCE_CATEGORIES and b.category != "file_read"]
    readers = [(i, b) for i, b in enumerate(behaviors) if b.category == "file_read"]
    sinks = [(i, b) for i, b in enumerate(behaviors) if b.category in SINK_CATEGORIES]
    for entry, reachable in paths.items():
        for si, sink in sinks:
            if sink.node not in reachable:
                continue
            for oi, source in [*sources, *readers]:
                if source.node not in reachable or (oi, si) in seen:
                    continue
                same_function = source.node == sink.node
                if source.category == "file_read" and not same_function:
                    continue  # reading files and using the network separately is too common to flag
                seen.add((oi, si))
                evidence = "dataflow" if (sink.file, sink.line) in tainted_sinks and same_function else "reachable"
                flows.append(CompositeFlow(source=source, sink=sink, entry=entry, evidence=evidence))
    flows.sort(key=lambda flow: (flow.evidence != "dataflow", flow.sink.file, flow.sink.line))
    return flows


def _short(node: str) -> str:
    file, _, name = node.partition("::")
    return f"{file}:{name}"
