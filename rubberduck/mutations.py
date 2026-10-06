"""Custom seeders for the three bug classes MutPy does not implement.

MutPy can rewrite operators and constants, but it does not swap a variable for
another variable, a dictionary key for another key, or the collection a loop
walks. Each operator below edits a single span in place, so the reported line
is still the line the developer would see.
"""

from __future__ import annotations

import ast

from rubberduck.models import Mutation

OPERATORS = ("variable_swap", "dict_key_swap", "loop_iterable_swap")

_SKIP_NAMES = {
    "self",
    "cls",
    "True",
    "False",
    "None",
    "len",
    "range",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sorted",
    "list",
    "dict",
    "set",
    "tuple",
    "str",
    "int",
    "float",
    "bool",
    "print",
    "isinstance",
    "issubclass",
    "type",
    "super",
    "getattr",
    "setattr",
    "hasattr",
    "min",
    "max",
    "sum",
    "any",
    "all",
    "open",
    "repr",
    "abs",
    "round",
    "iter",
    "next",
    "reversed",
}


def apply_operator(source: str, operator: str) -> Mutation | None:
    functions = {
        "variable_swap": variable_swap,
        "dict_key_swap": dict_key_swap,
        "loop_iterable_swap": loop_iterable_swap,
    }
    try:
        return functions[operator](source)
    except SyntaxError:
        return None


def variable_swap(source: str) -> Mutation | None:
    """Replace one use of a name with a different name from the same function."""
    tree = ast.parse(source)
    for function in _functions(tree):
        loads = [
            node
            for node in _walk_body(function)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and _usable_name(node.id)
        ]
        order: list[str] = []
        for node in loads:
            if node.id not in order:
                order.append(node.id)
        if len(order) < 2:
            continue
        target = next(node for node in loads if node.id == order[0])
        replacement = order[1]
        mutated = _replace(source, target, replacement)
        if mutated is None:
            continue
        return Mutation(
            operator="variable_swap",
            source=mutated,
            line=target.lineno,
            description=f"swapped variable {order[0]!r} to {replacement!r}",
        )
    return None


def dict_key_swap(source: str) -> Mutation | None:
    """Replace one string key with another string key from the same function."""
    tree = ast.parse(source)
    for function in _functions(tree):
        keys = _string_keys(function)
        distinct: list[ast.Constant] = []
        for key in keys:
            if all(existing.value != key.value for existing in distinct):
                distinct.append(key)
        if len(distinct) < 2:
            continue
        target = distinct[0]
        replacement = distinct[1].value
        mutated = _replace(source, target, repr(replacement))
        if mutated is None:
            continue
        return Mutation(
            operator="dict_key_swap",
            source=mutated,
            line=target.lineno,
            description=f"swapped dict key {target.value!r} to {replacement!r}",
        )
    return None


def loop_iterable_swap(source: str) -> Mutation | None:
    """Point a for-loop at a different name than the collection it iterates."""
    tree = ast.parse(source)
    for function in _functions(tree):
        parameters = [
            arg.arg
            for arg in function.args.args
            if _usable_name(arg.arg)
        ]
        for node in _walk_body(function):
            if not isinstance(node, (ast.For, ast.AsyncFor)):
                continue
            if not isinstance(node.iter, ast.Name):
                continue
            targets = {
                name.id
                for name in ast.walk(node.target)
                if isinstance(name, ast.Name)
            }
            replacement = _loop_replacement(function, node.iter.id, targets, parameters)
            if replacement is None:
                continue
            mutated = _replace(source, node.iter, replacement)
            if mutated is None:
                continue
            return Mutation(
                operator="loop_iterable_swap",
                source=mutated,
                line=node.iter.lineno,
                description=f"swapped loop iterable {node.iter.id!r} to {replacement!r}",
            )
    return None


def _loop_replacement(
    function: ast.AST,
    current: str,
    targets: set[str],
    parameters: list[str],
) -> str | None:
    loaded: list[str] = []
    for node in _walk_body(function):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and _usable_name(node.id)
            and node.id not in loaded
        ):
            loaded.append(node.id)
    for candidate in [*parameters, *loaded]:
        if candidate != current and candidate not in targets:
            return candidate
    return None


def _string_keys(function: ast.AST) -> list[ast.Constant]:
    keys: list[ast.Constant] = []
    for node in _walk_body(function):
        if isinstance(node, ast.Subscript):
            key = _subscript_key(node)
            if key is not None:
                keys.append(key)
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.lineno == key.end_lineno:
                    keys.append(key)
    return keys


def _subscript_key(node: ast.Subscript) -> ast.Constant | None:
    index = node.slice
    if isinstance(index, ast.Constant) and isinstance(index.value, str) and index.lineno == index.end_lineno:
        return index
    return None


def _functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _walk_body(function: ast.AST):
    body = getattr(function, "body", [])
    for statement in body:
        yield from _walk_statement(statement)


def _walk_statement(node: ast.AST):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_statement(child)


def _usable_name(name: str) -> bool:
    return name not in _SKIP_NAMES and not name.startswith("__")


def _replace(source: str, node: ast.AST, text: str) -> str | None:
    if node.lineno != node.end_lineno or node.end_col_offset is None:
        return None
    lines = source.splitlines(keepends=True)
    index = node.lineno - 1
    if index < 0 or index >= len(lines):
        return None
    line = lines[index]
    start = node.col_offset
    end = node.end_col_offset
    if start < 0 or end > len(line.rstrip("\r\n")):
        return None
    lines[index] = line[:start] + text + line[end:]
    mutated = "".join(lines)
    if mutated == source:
        return None
    try:
        ast.parse(mutated)
    except SyntaxError:
        return None
    return mutated
