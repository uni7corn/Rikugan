"""Bulk function renaming engine with quick and deep analysis modes."""

from __future__ import annotations

import queue
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..core.config import RikuganConfig
from ..core.logging import log_debug, log_error, log_info
from ..core.types import Message, Role
from ..providers.base import LLMProvider
from ..skills.registry import SkillRegistry
from ..tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

QUICK_ANALYSIS_PROMPT = """\
You are a reverse engineering assistant specializing in function naming.

Below are decompiled functions from a binary. For each function, suggest a
descriptive name based on its behavior. Use snake_case naming convention.

Rules:
- Analyze what each function does and give it a meaningful name
- Use prefixes like init_, parse_, send_, recv_, encrypt_, decrypt_, alloc_,
  free_, check_, validate_, handle_, dispatch_, etc.
- If a function is a wrapper, name it after what it wraps (e.g. wrapped_malloc)
- If a function's purpose is unclear, use a descriptive name like
  process_buffer_at_offset rather than unknown_func

Output format: one line per function, exactly:
0x<address> <new_name>

Do NOT include any other text, explanations, or markdown formatting.
Only output the address-name pairs.

Functions to analyze:
"""

DEEP_ANALYSIS_PROMPT = """\
You are a reverse engineering expert. Analyze this function in depth.

Examine:
1. All callers and callees (decompile them if needed)
2. String references
3. API imports used
4. Data structures accessed
5. Control flow patterns

Based on your thorough analysis, determine the function's purpose and
suggest a single descriptive name using snake_case convention.

Your final line of output MUST be exactly:
RENAME: 0x<address> <new_name>

Function to analyze:
"""

# ---------------------------------------------------------------------------
# Auto-generated name patterns to skip
# ---------------------------------------------------------------------------

_AUTO_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^sub_[0-9a-fA-F]+$"),
    re.compile(r"^FUN_[0-9a-fA-F]+$"),
    re.compile(r"^func_[0-9a-fA-F]+$"),
    re.compile(r"^unnamed_[0-9a-fA-F]+$"),
    re.compile(r"^loc_[0-9a-fA-F]+$"),
]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class RenameStatus(str, Enum):
    PENDING = "pending"
    DECOMPILING = "decompiling"
    ANALYZING = "analyzing"
    RENAMING = "renaming"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class RenameJob:
    """A single function rename request."""

    address: int
    current_name: str
    new_name: str = ""
    status: RenameStatus = RenameStatus.PENDING
    error: str = ""
    decompiled_code: str = ""


class RenameEventType(str, Enum):
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_ERROR = "job_error"
    BATCH_PROGRESS = "batch_progress"
    ALL_DONE = "all_done"


@dataclass
class RenameEvent:
    """Event emitted during bulk renaming."""

    type: RenameEventType
    address: int = 0
    current_name: str = ""
    new_name: str = ""
    error: str = ""
    completed: int = 0
    total: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class BulkRenamerEngine:
    """Bulk function renaming with quick and deep analysis modes.

    Quick mode: batch N functions into a single LLM prompt, parse results
    as lines of ``0x<addr> <name>``.

    Deep mode: spawn a SubagentRunner per function via ThreadPoolExecutor
    for thorough multi-turn analysis.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        config: RikuganConfig,
        host_name: str = "IDA Pro",
        skill_registry: SkillRegistry | None = None,
        batch_size: int = 10,
        max_workers: int = 3,
    ) -> None:
        self._provider = provider
        self._tools = tool_registry
        self._config = config
        self._host_name = host_name
        self._skills = skill_registry
        self._batch_size = batch_size
        self._max_workers = max_workers

        self._jobs: list[RenameJob] = []
        self._original_names: dict[int, str] = {}
        self._event_queue: queue.Queue[RenameEvent] = queue.Queue()
        self._cancel = threading.Event()
        self._paused = threading.Event()
        self._paused.set()  # not paused initially
        self._thread: threading.Thread | None = None

    def enqueue(self, jobs: list[RenameJob]) -> None:
        """Add jobs to the rename queue."""
        for job in jobs:
            if self.should_skip(job.current_name):
                self._jobs.append(job)
                self._original_names[job.address] = job.current_name
            else:
                job.status = RenameStatus.SKIPPED
                self._jobs.append(job)

    def start(self, deep: bool = False) -> None:
        """Start the renaming engine in a background thread.

        Parameters
        ----------
        deep : bool
            If True, use deep analysis mode (one subagent per function).
            If False, use quick mode (batch prompting).
        """
        self._cancel.clear()
        self._paused.set()
        self._thread = threading.Thread(
            target=self._run_deep if deep else self._run_quick,
            daemon=True,
            name="rikugan-bulk-renamer",
        )
        self._thread.start()
        log_info(f"Bulk renamer started: {len(self._pending_jobs())} jobs, mode={'deep' if deep else 'quick'}")

    def poll_event(self) -> RenameEvent | None:
        """Non-blocking poll for the next rename event."""
        try:
            return self._event_queue.get_nowait()
        except queue.Empty:
            return None

    def pause(self) -> None:
        """Pause the renaming engine."""
        self._paused.clear()
        log_info("Bulk renamer paused")

    def resume(self) -> None:
        """Resume the renaming engine."""
        self._paused.set()
        log_info("Bulk renamer resumed")

    def cancel(self) -> None:
        """Cancel the renaming engine."""
        self._cancel.set()
        self._paused.set()  # unblock if paused
        log_info("Bulk renamer cancelled")

    def undo_all(self) -> None:
        """Revert all completed renames to their original names."""
        reverted = 0
        for job in self._jobs:
            if job.status == RenameStatus.COMPLETED and job.address in self._original_names:
                original = self._original_names[job.address]
                try:
                    self._tools.execute(
                        "rename_function",
                        {"address": f"0x{job.address:x}", "new_name": original},
                    )
                    reverted += 1
                    log_debug(f"Reverted 0x{job.address:x} from {job.new_name!r} to {original!r}")
                except Exception as e:
                    log_error(f"Failed to revert 0x{job.address:x}: {e}")
        log_info(f"Undo complete: reverted {reverted} renames")

    @staticmethod
    def should_skip(name: str) -> bool:
        """Return True if the name looks auto-generated and should be renamed.

        Note: returns True for names that *should* be processed (i.e., are
        auto-generated), False for names that look human-assigned.
        """
        for pattern in _AUTO_NAME_PATTERNS:
            if pattern.match(name):
                return True
        return False

    # -- Internal helpers ------------------------------------------------------

    def _pending_jobs(self) -> list[RenameJob]:
        """Return jobs that are still pending."""
        return [j for j in self._jobs if j.status == RenameStatus.PENDING]

    def _run_quick(self) -> None:
        """Quick mode: batch functions into single prompts."""
        pending = self._pending_jobs()
        total = len(pending)
        completed = 0

        for batch_start in range(0, total, self._batch_size):
            if self._cancel.is_set():
                break

            # Wait if paused
            self._paused.wait()
            if self._cancel.is_set():
                break

            batch = pending[batch_start : batch_start + self._batch_size]

            # Decompile all functions in the batch
            prompt_parts: list[str] = []
            valid_jobs: list[RenameJob] = []
            for job in batch:
                job.status = RenameStatus.DECOMPILING
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_STARTED,
                        address=job.address,
                        current_name=job.current_name,
                    )
                )
                try:
                    result = self._tools.execute(
                        "decompile_function",
                        {"address": f"0x{job.address:x}"},
                    )
                    job.decompiled_code = result
                    prompt_parts.append(
                        f"// Function at 0x{job.address:x} (current name: {job.current_name})\n{result}\n"
                    )
                    valid_jobs.append(job)
                except Exception as e:
                    job.status = RenameStatus.FAILED
                    job.error = str(e)
                    self._event_queue.put(
                        RenameEvent(
                            type=RenameEventType.JOB_ERROR,
                            address=job.address,
                            current_name=job.current_name,
                            error=str(e),
                        )
                    )
                    log_error(f"Decompile failed for 0x{job.address:x}: {e}")

            if not valid_jobs:
                continue

            # Build the batch prompt and call the LLM
            full_prompt = QUICK_ANALYSIS_PROMPT + "\n".join(prompt_parts)
            for job in valid_jobs:
                job.status = RenameStatus.ANALYZING

            try:
                names = self._quick_llm_call(full_prompt)
                self._apply_quick_results(valid_jobs, names)
            except Exception as e:
                for job in valid_jobs:
                    job.status = RenameStatus.FAILED
                    job.error = str(e)
                    self._event_queue.put(
                        RenameEvent(
                            type=RenameEventType.JOB_ERROR,
                            address=job.address,
                            current_name=job.current_name,
                            error=str(e),
                        )
                    )
                log_error(f"Quick analysis batch failed: {e}")

            completed += len(batch)
            self._event_queue.put(
                RenameEvent(
                    type=RenameEventType.BATCH_PROGRESS,
                    completed=completed,
                    total=total,
                )
            )

        self._event_queue.put(
            RenameEvent(
                type=RenameEventType.ALL_DONE,
                completed=sum(1 for j in self._jobs if j.status == RenameStatus.COMPLETED),
                total=total,
            )
        )
        log_info("Bulk renamer quick mode finished")

    def _quick_llm_call(self, prompt: str) -> dict[int, str]:
        """Call the LLM with a batch prompt and parse address-name pairs."""
        messages = [Message(role=Role.USER, content=prompt)]
        response = self._provider.chat(
            messages=messages,
            tools=None,
            temperature=0.2,
            max_tokens=2048,
        )

        results: dict[int, str] = {}
        addr_pattern = re.compile(r"^0x([0-9a-fA-F]+)\s+(\S+)$")
        for line in response.content.strip().splitlines():
            line = line.strip()
            match = addr_pattern.match(line)
            if match:
                addr = int(match.group(1), 16)
                name = match.group(2)
                results[addr] = name

        return results

    def _apply_quick_results(
        self,
        jobs: list[RenameJob],
        names: dict[int, str],
    ) -> None:
        """Apply parsed rename results to jobs."""
        for job in jobs:
            new_name = names.get(job.address)
            if not new_name:
                job.status = RenameStatus.FAILED
                job.error = "No name suggested by LLM"
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_ERROR,
                        address=job.address,
                        current_name=job.current_name,
                        error=job.error,
                    )
                )
                continue

            job.new_name = new_name
            job.status = RenameStatus.RENAMING
            try:
                self._tools.execute(
                    "rename_function",
                    {"address": f"0x{job.address:x}", "new_name": new_name},
                )
                job.status = RenameStatus.COMPLETED
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_COMPLETED,
                        address=job.address,
                        current_name=job.current_name,
                        new_name=new_name,
                    )
                )
                log_debug(f"Renamed 0x{job.address:x}: {job.current_name!r} -> {new_name!r}")
            except Exception as e:
                job.status = RenameStatus.FAILED
                job.error = str(e)
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_ERROR,
                        address=job.address,
                        current_name=job.current_name,
                        error=str(e),
                    )
                )
                log_error(f"Rename failed for 0x{job.address:x}: {e}")

    def _run_deep(self) -> None:
        """Deep mode: one SubagentRunner per function via ThreadPoolExecutor."""
        from .subagent import SubagentRunner  # deferred to avoid circular import

        pending = self._pending_jobs()
        total = len(pending)
        completed_count = 0
        rename_pattern = re.compile(r"RENAME:\s*0x([0-9a-fA-F]+)\s+(\S+)")

        def _analyze_one(job: RenameJob) -> None:
            nonlocal completed_count

            if self._cancel.is_set():
                return

            self._paused.wait()
            if self._cancel.is_set():
                return

            job.status = RenameStatus.DECOMPILING
            self._event_queue.put(
                RenameEvent(
                    type=RenameEventType.JOB_STARTED,
                    address=job.address,
                    current_name=job.current_name,
                )
            )

            # Decompile first
            try:
                result = self._tools.execute(
                    "decompile_function",
                    {"address": f"0x{job.address:x}"},
                )
                job.decompiled_code = result
            except Exception as e:
                job.status = RenameStatus.FAILED
                job.error = str(e)
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_ERROR,
                        address=job.address,
                        current_name=job.current_name,
                        error=str(e),
                    )
                )
                return

            # Run deep analysis via subagent
            job.status = RenameStatus.ANALYZING
            task = (
                f"{DEEP_ANALYSIS_PROMPT}\n"
                f"// Function at 0x{job.address:x} (current name: {job.current_name})\n"
                f"{job.decompiled_code}"
            )

            runner = SubagentRunner(
                provider=self._provider,
                tool_registry=self._tools,
                config=self._config,
                host_name=self._host_name,
                skill_registry=self._skills,
            )

            final_text = ""
            try:
                for event in runner.run_task(task, max_turns=10):
                    if self._cancel.is_set():
                        return
                    if event.type.value == "text_done" and event.text:
                        final_text = event.text
            except Exception as e:
                job.status = RenameStatus.FAILED
                job.error = str(e)
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_ERROR,
                        address=job.address,
                        current_name=job.current_name,
                        error=str(e),
                    )
                )
                return

            # Parse the RENAME line from the subagent output
            match = rename_pattern.search(final_text)
            if not match:
                job.status = RenameStatus.FAILED
                job.error = "No RENAME line found in subagent output"
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_ERROR,
                        address=job.address,
                        current_name=job.current_name,
                        error=job.error,
                    )
                )
                return

            new_name = match.group(2)
            job.new_name = new_name
            job.status = RenameStatus.RENAMING

            try:
                self._tools.execute(
                    "rename_function",
                    {"address": f"0x{job.address:x}", "new_name": new_name},
                )
                job.status = RenameStatus.COMPLETED
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_COMPLETED,
                        address=job.address,
                        current_name=job.current_name,
                        new_name=new_name,
                    )
                )
                log_debug(f"Deep renamed 0x{job.address:x}: {job.current_name!r} -> {new_name!r}")
            except Exception as e:
                job.status = RenameStatus.FAILED
                job.error = str(e)
                self._event_queue.put(
                    RenameEvent(
                        type=RenameEventType.JOB_ERROR,
                        address=job.address,
                        current_name=job.current_name,
                        error=str(e),
                    )
                )
                log_error(f"Deep rename failed for 0x{job.address:x}: {e}")

            completed_count += 1
            self._event_queue.put(
                RenameEvent(
                    type=RenameEventType.BATCH_PROGRESS,
                    completed=completed_count,
                    total=total,
                )
            )

        with ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="rikugan-deep-rename",
        ) as executor:
            futures = [executor.submit(_analyze_one, job) for job in pending]
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    log_error(f"Deep rename worker error: {e}")

        self._event_queue.put(
            RenameEvent(
                type=RenameEventType.ALL_DONE,
                completed=sum(1 for j in self._jobs if j.status == RenameStatus.COMPLETED),
                total=total,
            )
        )
        log_info("Bulk renamer deep mode finished")
