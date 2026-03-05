"""Tests for rikugan.ui.message_widgets — pure logic helpers."""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# PySide6 stubs
# ---------------------------------------------------------------------------

def _qt_class(name: str) -> type:
    return type(name, (), {"__init__": lambda self, *a, **k: None})


class _Signal:
    def __init__(self, *a): pass
    def connect(self, *a): pass
    def disconnect(self, *a): pass
    def emit(self, *a): pass
    def __get__(self, obj, objtype=None): return self


_widget_names = [
    "QApplication", "QWidget", "QVBoxLayout", "QHBoxLayout", "QLabel",
    "QPushButton", "QPlainTextEdit", "QScrollArea", "QFrame", "QSplitter",
    "QDialog", "QDialogButtonBox", "QComboBox", "QLineEdit", "QSpinBox",
    "QDoubleSpinBox", "QCheckBox", "QGroupBox", "QFormLayout",
    "QToolButton", "QSizePolicy", "QTabWidget", "QTabBar",
    "QFileDialog", "QMenu", "QMessageBox",
]

_core_mod = types.ModuleType("PySide6.QtCore")
_core_mod.Signal = _Signal
_core_mod.Qt = MagicMock()
_core_mod.QObject = _qt_class("QObject")
_core_mod.QTimer = _qt_class("QTimer")

_widget_mod = types.ModuleType("PySide6.QtWidgets")
for _n in _widget_names:
    setattr(_widget_mod, _n, _qt_class(_n))

_gui_mod = types.ModuleType("PySide6.QtGui")
for _n in ["QSyntaxHighlighter", "QTextCharFormat", "QColor", "QFont"]:
    setattr(_gui_mod, _n, _qt_class(_n))

sys.modules.setdefault("PySide6", types.ModuleType("PySide6"))
sys.modules.setdefault("PySide6.QtCore", _core_mod)
sys.modules.setdefault("PySide6.QtWidgets", _widget_mod)
sys.modules.setdefault("PySide6.QtGui", _gui_mod)

from rikugan.ui.message_widgets import _split_thinking  # noqa: E402


# ---------------------------------------------------------------------------
# _split_thinking
# ---------------------------------------------------------------------------

class TestSplitThinking(unittest.TestCase):
    def test_no_think_tags_returns_all_visible(self):
        thinking, visible = _split_thinking("Hello world")
        self.assertEqual(thinking, "")
        self.assertEqual(visible, "Hello world")

    def test_complete_think_block_extracted(self):
        thinking, visible = _split_thinking("Before <think>reasoning</think> After")
        self.assertEqual(thinking, "reasoning")
        self.assertEqual(visible, "Before  After".strip())

    def test_visible_part_stripped(self):
        thinking, visible = _split_thinking("<think>A</think>   result   ")
        self.assertEqual(visible, "result")

    def test_multiple_think_blocks(self):
        text = "<think>step1</think> middle <think>step2</think> end"
        thinking, visible = _split_thinking(text)
        self.assertIn("step1", thinking)
        self.assertIn("step2", thinking)
        self.assertIn("end", visible)

    def test_empty_string(self):
        thinking, visible = _split_thinking("")
        self.assertEqual(thinking, "")
        self.assertEqual(visible, "")

    def test_unclosed_think_tag_partial_streaming(self):
        text = "Before <think>partial reasoning"
        thinking, visible = _split_thinking(text)
        self.assertIn("partial reasoning", thinking)
        self.assertEqual(visible, "Before")

    def test_empty_think_block(self):
        thinking, visible = _split_thinking("<think></think> result")
        self.assertEqual(thinking, "")
        self.assertEqual(visible, "result")

    def test_think_whitespace_stripped(self):
        thinking, visible = _split_thinking("<think>  trimmed  </think> x")
        self.assertEqual(thinking, "trimmed")

    def test_multiline_think_block(self):
        text = "<think>\nline1\nline2\n</think> visible"
        thinking, visible = _split_thinking(text)
        self.assertIn("line1", thinking)
        self.assertIn("line2", thinking)
        self.assertEqual(visible, "visible")

    def test_no_visible_content_after_think(self):
        thinking, visible = _split_thinking("<think>inner</think>")
        self.assertEqual(thinking, "inner")
        self.assertEqual(visible, "")

    def test_unclosed_think_empty_partial(self):
        text = "Before <think>"
        thinking, visible = _split_thinking(text)
        self.assertEqual(thinking, "")  # empty partial not added
        self.assertEqual(visible, "Before")


if __name__ == "__main__":
    unittest.main()
