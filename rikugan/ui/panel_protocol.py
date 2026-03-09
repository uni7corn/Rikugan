"""Shared host-panel interface contract.

Both IDA and Binary Ninja panel wrappers implement this protocol so that
host integration code can rely on a single, typed contract instead of
``hasattr`` probes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HostPanel(Protocol):
    """Public API that every host panel wrapper must expose."""

    def prefill_input(self, text: str, auto_submit: bool = False) -> None:
        """Pre-fill the chat input box, optionally auto-submitting."""
        ...

    def shutdown(self) -> None:
        """Shut the panel down, releasing resources."""
        ...

    def on_database_changed(self, new_path: str) -> None:
        """Notify the panel that the active database/binary changed."""
        ...
