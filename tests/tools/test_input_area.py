"""Tests for rikugan.ui.input_area — pure logic helpers."""

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

from rikugan.ui.input_area import InputArea, _SkillPopup  # noqa: E402


# ---------------------------------------------------------------------------
# _SkillPopup — pure list logic
# ---------------------------------------------------------------------------

def _make_popup() -> _SkillPopup:
    popup = object.__new__(_SkillPopup)
    popup._slugs = []
    popup._selected_idx = 0
    popup._items = []
    return popup


class TestSkillPopupCurrentSlug(unittest.TestCase):
    def test_empty_list_returns_none(self):
        popup = _make_popup()
        self.assertIsNone(popup.current_slug())

    def test_returns_first_item_by_default(self):
        popup = _make_popup()
        popup._slugs = ["plan", "modify", "explore"]
        self.assertEqual(popup.current_slug(), "plan")

    def test_returns_selected_item(self):
        popup = _make_popup()
        popup._slugs = ["a", "b", "c"]
        popup._selected_idx = 2
        self.assertEqual(popup.current_slug(), "c")

    def test_out_of_bounds_idx_returns_none(self):
        popup = _make_popup()
        popup._slugs = ["a"]
        popup._selected_idx = 5
        self.assertIsNone(popup.current_slug())


class TestSkillPopupIsEmpty(unittest.TestCase):
    def test_empty_list(self):
        popup = _make_popup()
        self.assertTrue(popup.is_empty())

    def test_non_empty_list(self):
        popup = _make_popup()
        popup._slugs = ["plan"]
        self.assertFalse(popup.is_empty())


class TestSkillPopupMoveSelection(unittest.TestCase):
    def test_wraps_forward(self):
        popup = _make_popup()
        popup._slugs = ["a", "b", "c"]
        popup._selected_idx = 2
        popup._update_highlight = MagicMock()
        popup.move_selection(1)
        self.assertEqual(popup._selected_idx, 0)

    def test_wraps_backward(self):
        popup = _make_popup()
        popup._slugs = ["a", "b", "c"]
        popup._selected_idx = 0
        popup._update_highlight = MagicMock()
        popup.move_selection(-1)
        self.assertEqual(popup._selected_idx, 2)

    def test_no_move_when_empty(self):
        popup = _make_popup()
        popup._selected_idx = 0
        popup._update_highlight = MagicMock()
        popup.move_selection(1)
        self.assertEqual(popup._selected_idx, 0)


# ---------------------------------------------------------------------------
# InputArea — pure logic methods
# ---------------------------------------------------------------------------

def _make_input() -> InputArea:
    area = object.__new__(InputArea)
    area._enabled = True
    area._skill_slugs = []
    area._popup = None
    area._submit_callback = None
    area._cancel_callback = None
    return area


class TestInputAreaSetCallbacks(unittest.TestCase):
    def test_set_submit_callback(self):
        area = _make_input()
        cb = MagicMock()
        area.set_submit_callback(cb)
        self.assertIs(area._submit_callback, cb)

    def test_set_cancel_callback(self):
        area = _make_input()
        cb = MagicMock()
        area.set_cancel_callback(cb)
        self.assertIs(area._cancel_callback, cb)


class TestInputAreaSetSkillSlugs(unittest.TestCase):
    def test_includes_builtin_commands(self):
        area = _make_input()
        area.set_skill_slugs([])
        self.assertIn("plan", area._skill_slugs)
        self.assertIn("modify", area._skill_slugs)
        self.assertIn("explore", area._skill_slugs)

    def test_merges_custom_slugs(self):
        area = _make_input()
        area.set_skill_slugs(["decompile", "rename"])
        self.assertIn("decompile", area._skill_slugs)
        self.assertIn("rename", area._skill_slugs)

    def test_result_is_sorted(self):
        area = _make_input()
        area.set_skill_slugs(["z", "a", "m"])
        self.assertEqual(area._skill_slugs, sorted(area._skill_slugs))

    def test_no_duplicates(self):
        area = _make_input()
        area.set_skill_slugs(["plan", "plan", "explore"])
        self.assertEqual(area._skill_slugs.count("plan"), 1)


class TestInputAreaCheckAutocomplete(unittest.TestCase):
    def test_no_slash_dismisses_popup(self):
        area = _make_input()
        area._skill_slugs = ["plan"]
        area._dismiss_popup = MagicMock()
        area.toPlainText = MagicMock(return_value="hello")
        area._check_autocomplete()
        area._dismiss_popup.assert_called_once()

    def test_slash_with_space_dismisses_popup(self):
        area = _make_input()
        area._skill_slugs = ["plan"]
        area._dismiss_popup = MagicMock()
        area.toPlainText = MagicMock(return_value="/plan some text")
        area._check_autocomplete()
        area._dismiss_popup.assert_called_once()

    def test_partial_slug_shows_popup(self):
        area = _make_input()
        area._skill_slugs = ["plan", "modify"]
        area._show_popup = MagicMock()
        area._dismiss_popup = MagicMock()
        area.toPlainText = MagicMock(return_value="/pl")
        area._check_autocomplete()
        area._show_popup.assert_called_once_with(["plan"])

    def test_no_match_dismisses_popup(self):
        area = _make_input()
        area._skill_slugs = ["plan", "modify"]
        area._dismiss_popup = MagicMock()
        area.toPlainText = MagicMock(return_value="/xyz")
        area._check_autocomplete()
        area._dismiss_popup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
