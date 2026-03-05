---
name: Deobfuscation
description: Systematic deobfuscation — string decryption, CFF removal, opaque predicates, MBA simplification
tags: [deobfuscation, obfuscation, cff, mba, opaque-predicates]
mode: plan
---
# Deobfuscation Mode

Deobfuscate fully first. Analyze afterward.
NEVER analyze obfuscated code and draw conclusions — it misleads.

## Order of Operations

### 1. String Decryption (always first — unlocks context, unless user asked for SPECIFIC deobfuscation)

Strings are the fastest path to understanding.

1. Check for readable strings. If very few in a large binary → strings are encrypted.
2. Find the string decode stub: a small function called before every string use.
3. Decompile it, identify the algorithm (XOR, RC4, custom).
4. Use xrefs on the decode function to find all encrypted string call sites.
5. Decrypted strings give you: C2 addresses, file paths, registry keys, API names.

### 2. Structural Deobfuscation

**You are the deobfuscator.** Read the IL, understand what the obfuscation is doing, and use the write primitives to undo it. The tools give you read/write access to IL — you decide what to change.

#### How to read IL

- `get_il` — read IL at any level (LLIL, MLIL, HLIL). MLIL is the most useful for deobfuscation: it has typed variables, SSA form, and shows data flow clearly.
- `get_cfg` — read CFG structure (blocks, edges, back edges, dominators, loops). This tells you the shape of the function.
- `track_variable_ssa` — trace a variable through SSA def-use chains. See every assignment, every use, every constant value.
- `decompile_function` — read the decompiled C. After each modification, redecompile to verify improvement.
- `get_il_block` — read a single IL block's instructions.

#### How to write IL

- `il_set_condition` — force a conditional branch to always-true or always-false. Use this to eliminate opaque predicates and force dispatcher branches.
- `il_nop_expr` — NOP an IL expression by index. Use this to remove state variable assignments, dead stores, junk computations.
- `il_replace_expr` — replace an IL expression with a constant, NOP, or copy of another expression. Use this for MBA simplification (replace complex expression with simplified result).
- `il_remove_block` — NOP all instructions in a basic block. Use this to eliminate dead code blocks.
- `nop_instructions` — NOP machine code bytes at an address range. Use this when IL-level modification isn't sufficient and you need to patch the underlying bytes.
- `patch_branch` — force/invert/unconditional a conditional branch at byte level (x86 only). Fallback when IL-level condition forcing doesn't work.
- `write_bytes` — write arbitrary bytes. Last resort escape hatch.
- `redecompile_function` — force redecompilation after modifications.

#### How to batch-transform

- `install_il_workflow` — register a Python transform as a BN workflow activity. The transform runs in the analysis pipeline for every function. Use this when you identify a recurring pattern across many functions (e.g., the same opaque predicate template everywhere). Write the Python transform code yourself.

### What obfuscation looks like in IL

#### Control Flow Flattening (CFF)

**What it is:** The original linear control flow is replaced with a dispatcher loop. A state variable determines which block executes next.

**What it looks like in IL:**
- A loop with a back edge to a header block
- The header block compares a variable against multiple constants (if-else chain or switch)
- Each case body assigns a new constant to the same variable (the state variable)
- The variable may be a named var (`var_18 = 0x25`) or a memory store (`[rbp - 0x10].d = 0x25`) depending on optimization level

**How to remove it:**
1. Read the IL with `get_il`. Identify the state variable and the dispatcher pattern.
2. Read the CFG with `get_cfg`. Find the back edge (dispatcher loop) and all case blocks.
3. Map the state machine: for each case, what state value triggers it, and what state value does it assign next? This gives you the original execution order.
4. NOP all state variable assignments with `il_nop_expr` — they're dispatcher bookkeeping.
5. Force or NOP the dispatcher back edge so control falls through linearly.
6. NOP/remove dead code blocks (unreachable states, dispatcher overhead).
7. Redecompile to verify. The function should now read as linear code.

**-O0 gotcha:** At -O0, the compiler uses memory stores instead of variable assignments. The state variable appears as `[rbp - 0x10].d = 0x25` (STORE) rather than `var_18 = 0x25` (SET_VAR). The comparisons may use temporaries: `temp0 = [rbp - 0x10].d; if (temp0 == 0x10)`. Track by matching the memory expression, not the variable name.

#### Opaque Predicates

**What it is:** Conditions that always evaluate to the same value but look non-trivial.

**What it looks like in IL:**
- Algebraic: `x * (x-1) % 2 == 0` — always true
- Constant-returning functions: `if (always_true())` — a function that trivially returns a constant
- BN may already resolve some to `if (true)` or `if (false)` — check HLIL

**How to remove:** Use `il_set_condition` to force the branch to the always-taken direction. Then the dead branch becomes unreachable — remove it with `il_remove_block` or `il_nop_expr`.

#### Mixed Boolean-Arithmetic (MBA)

**What it is:** Simple operations disguised as complex boolean-arithmetic expressions.

**Common identities:**
- `(x ^ y) + 2*(x & y)` = `x + y`
- `(x | y) - (x & ~y)` = `y`
- `(x & y) | (x & ~y)` = `x`
- `~(~x & ~y)` = `x | y`

**How to remove:** Identify the simplified form, then use `il_replace_expr` to swap the complex expression with a simpler one (constant or smaller expression). Work bottom-up: simplify innermost MBA expressions first.

#### Junk Code / Dead Stores

**What it is:** Instructions that compute values never used, or stores to locations never read.

**How to identify:** Track variables with `track_variable_ssa`. If a variable version has no uses, its definition is dead. If a block has no live successors and no side effects, it's dead.

**How to remove:** `il_nop_expr` the dead instructions.

### 3. VM Boundary (if detected)

VM virtualization is NOT deobfuscatable with IL tools.
1. Identify the VM entry point, bytecode buffer, handler table.
2. Document: entry address, bytecode location, handler table address, handler count.
3. Focus analysis on non-virtualized code paths.
4. Recommend specialized VM lifting tooling to the user.

### 4. Post-Deobfuscation

After all deobfuscation:
- Redecompile all modified functions.
- The code should now be readable. If it isn't, check for more obfuscation layers.
- Proceed with normal analysis.

## Critical Rules

- Read the IL before acting. Spend 1 tool call to understand the obfuscation rather than 20 guessing.
- String decryption ALWAYS comes first.
- After each modification, redecompile to verify improvement.
- If a tool-based approach isn't working, fall back to byte-level patching (`nop_instructions`, `patch_branch`, `write_bytes`).
- You are the deobfuscator. The tools are your hands. Read, understand, modify, verify.
