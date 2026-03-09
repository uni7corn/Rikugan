"""Shared helpers for Binary Ninja tool modules.

This module re-exports from focused sub-modules for backwards compatibility.
New code should import directly from the specific module:

- compat: get_bn_module, require_bv, call_compat, parse_addr_like, ...
- fn_utils: get_function_at, get_function_name, iter_functions, ...
- sym_utils: get_symbol_at, symbol_name, iter_symbols, rename_symbol_at, ...
- comment_utils: get_comment_at, set_comment_at
- disasm_utils: get_instruction_len, get_disassembly_line, ...
- type_utils: parse_type_string, define_user_type
"""

from __future__ import annotations


# Re-exports — keep for any external consumers
