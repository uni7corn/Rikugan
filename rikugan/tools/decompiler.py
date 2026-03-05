"""Hex-Rays decompiler tools."""

from __future__ import annotations

import importlib
from typing import Annotated

from ..constants import HAS_HEXRAYS as _HAS_HEXRAYS
from ..core.errors import ToolError
from .base import parse_addr, tool

ida_hexrays = ida_lines = None
try:
    ida_hexrays = importlib.import_module("ida_hexrays")
    ida_lines = importlib.import_module("ida_lines")
except ImportError:
    pass  # Hex-Rays not present — _HAS_HEXRAYS guard handles graceful degradation


def _decompile(ea: int):
    """Decompile at *ea*, returning the cfunc_t or a user-facing error string."""
    if not _HAS_HEXRAYS:
        raise ToolError("Hex-Rays decompiler is not available", tool_name="decompiler")
    try:
        cfunc = ida_hexrays.decompile(ea)
    except ida_hexrays.DecompilationFailure as e:
        return f"Decompilation failed at 0x{ea:x}: {e}"
    if cfunc is None:
        return f"Decompilation returned None for 0x{ea:x}"
    return cfunc


@tool(category="decompiler", requires_decompiler=True)
def decompile_function(address: Annotated[str, "Function address (hex string)"]) -> str:
    """Decompile the function at the given address and return pseudocode."""
    result = _decompile(parse_addr(address))
    return result if isinstance(result, str) else str(result)


@tool(category="decompiler", requires_decompiler=True)
def get_pseudocode(
    address: Annotated[str, "Function address (hex string)"],
    with_line_numbers: Annotated[bool, "Include line numbers"] = True,
) -> str:
    """Get the pseudocode of a function with optional line numbers."""
    result = _decompile(parse_addr(address))
    if isinstance(result, str):
        return result

    lines = []
    sv = result.get_pseudocode()
    for i, sl in enumerate(sv):
        text = ida_lines.tag_remove(sl.line)
        if with_line_numbers:
            lines.append(f"{i + 1:4d}  {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


@tool(category="decompiler", requires_decompiler=True)
def get_decompiler_variables(address: Annotated[str, "Function address (hex string)"]) -> str:
    """List local variables from the decompiler output."""
    result = _decompile(parse_addr(address))
    if isinstance(result, str):
        return result

    lines = ["Local variables:"]
    lvars = result.get_lvars()
    for lv in lvars:
        kind = "arg" if lv.is_arg_var else "local"
        tname = str(lv.type()) if lv.type() else "?"
        lines.append(f"  {kind:5s} {tname:20s} {lv.name}")

    return "\n".join(lines)
