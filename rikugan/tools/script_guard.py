"""Shared security patterns and execution helper for Python script execution tools."""

from __future__ import annotations

import ast
import contextlib
import io
from typing import Callable, Dict, Any

# Modules that must never be imported (directly or via __import__).
_BLOCKED_MODULES = frozenset({"subprocess", "shlex", "pty", "commands"})

# Built-in calls that must never appear.
_BLOCKED_CALLS = frozenset({"exec", "eval", "compile", "__import__"})

# Attribute calls that must never appear (module.func patterns).
_BLOCKED_ATTRS = frozenset({
    ("os", "system"),
    ("os", "popen"),
    ("os", "execl"),
    ("os", "execle"),
    ("os", "execlp"),
    ("os", "execlpe"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "execvp"),
    ("os", "execvpe"),
    ("os", "spawnl"),
    ("os", "spawnle"),
    ("os", "spawnlp"),
    ("os", "spawnlpe"),
    ("os", "spawnv"),
    ("os", "spawnve"),
    ("os", "spawnvp"),
    ("os", "spawnvpe"),
})


def _check_ast(code: str) -> str | None:
    """Parse code and walk the AST for blocked constructs.

    Returns an error message if a violation is found, or None if safe.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "Blocked — code contains a syntax error and cannot be validated"

    for node in ast.walk(tree):
        # Block: import subprocess / from subprocess import ...
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_MODULES:
                    return f"Blocked — import of disallowed module '{alias.name}'"

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in _BLOCKED_MODULES:
                    return f"Blocked — import from disallowed module '{node.module}'"

        # Block: exec(), eval(), compile(), __import__()
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _BLOCKED_CALLS:
                return f"Blocked — call to disallowed built-in '{func.id}()'"

            # Block: os.system(), os.popen(), os.exec*(), os.spawn*()
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                pair = (func.value.id, func.attr)
                if pair in _BLOCKED_ATTRS:
                    return f"Blocked — call to disallowed '{pair[0]}.{pair[1]}()'"
                # Catch os.exec*/os.spawn* variants not explicitly listed
                if func.value.id == "os" and (
                    func.attr.startswith("exec") or func.attr.startswith("spawn")
                ):
                    return f"Blocked — call to disallowed 'os.{func.attr}()'"

    return None


def run_guarded_script(code: str, namespace_factory: Callable[[], Dict[str, Any]]) -> str:
    """Block dangerous patterns, exec code, and return captured stdout/stderr."""
    violation = _check_ast(code)
    if violation:
        return f"Error: {violation}"

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    namespace = namespace_factory()

    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            exec(code, namespace)  # noqa: S102 — intentional scripting tool
        except Exception as e:
            stderr_buf.write(f"{type(e).__name__}: {e}\n")

    stdout = stdout_buf.getvalue()
    stderr = stderr_buf.getvalue()
    parts = []
    if stdout:
        parts.append(f"stdout:\n{stdout}")
    if stderr:
        parts.append(f"stderr:\n{stderr}")
    if not parts:
        parts.append("(no output)")
    return "\n".join(parts)
