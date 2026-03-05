"""Tests for rikugan.ui.plan_view — pure logic helpers."""

from __future__ import annotations

import sys
import types
import unittest
import unittest.mock
from unittest.mock import MagicMock, call


# ---------------------------------------------------------------------------
# Qt stubs
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

_qt_compat_mod = types.ModuleType("rikugan.ui.qt_compat")
for _n in _widget_names + ["QScrollArea", "QFrame", "QSplitter"]:
    setattr(_qt_compat_mod, _n, _qt_class(_n))
_qt_compat_mod.Signal = _Signal
_qt_compat_mod.Qt = MagicMock()
_qt_compat_mod.QTimer = _qt_class("QTimer")
sys.modules.setdefault("rikugan.ui.qt_compat", _qt_compat_mod)

from rikugan.ui.plan_view import PlanStepWidget, PlanView  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(index: int = 0, text: str = "step") -> PlanStepWidget:
    step = object.__new__(PlanStepWidget)
    step._index = index
    step._status = "pending"
    step._status_label = MagicMock()
    step.setObjectName = MagicMock()
    step.style = MagicMock(return_value=MagicMock())
    return step


def _make_view() -> PlanView:
    view = object.__new__(PlanView)
    view._steps = []
    view._steps_container = MagicMock()
    view._approve_btn = MagicMock()
    view._reject_btn = MagicMock()
    view._on_approved = None
    view._on_rejected = None
    return view


# ---------------------------------------------------------------------------
# PlanStepWidget.set_status
# ---------------------------------------------------------------------------

class TestPlanStepSetStatus(unittest.TestCase):
    def test_active_sets_triangle(self):
        step = _make_step()
        step.set_status("active")
        step._status_label.setText.assert_called_with("▶")

    def test_done_sets_checkmark(self):
        step = _make_step()
        step.set_status("done")
        step._status_label.setText.assert_called_with("✓")

    def test_error_sets_cross(self):
        step = _make_step()
        step.set_status("error")
        step._status_label.setText.assert_called_with("✗")

    def test_skipped_sets_dash(self):
        step = _make_step()
        step.set_status("skipped")
        step._status_label.setText.assert_called_with("−")

    def test_pending_sets_circle(self):
        step = _make_step()
        step.set_status("pending")
        step._status_label.setText.assert_called_with("○")

    def test_unknown_status_sets_circle(self):
        step = _make_step()
        step.set_status("unknown_status")
        step._status_label.setText.assert_called_with("○")

    def test_status_stored(self):
        step = _make_step()
        step.set_status("done")
        self.assertEqual(step._status, "done")

    def test_active_sets_object_name(self):
        step = _make_step()
        step.set_status("active")
        step.setObjectName.assert_called_with("plan_step_active")

    def test_done_sets_object_name(self):
        step = _make_step()
        step.set_status("done")
        step.setObjectName.assert_called_with("plan_step_done")

    def test_pending_resets_object_name(self):
        step = _make_step()
        step.set_status("pending")
        step.setObjectName.assert_called_with("plan_step")


# ---------------------------------------------------------------------------
# PlanView.set_plan
# ---------------------------------------------------------------------------

class TestPlanViewSetPlan(unittest.TestCase):
    def _patched_view(self):
        """Return a PlanView with PlanStepWidget patched to a MagicMock."""
        from rikugan.ui import plan_view as _pv
        mock_step_cls = MagicMock(side_effect=lambda i, t, **kw: MagicMock())
        return _make_view(), mock_step_cls, _pv

    def test_set_plan_adds_steps(self):
        import rikugan.ui.plan_view as pv
        with unittest.mock.patch.object(pv, "PlanStepWidget", side_effect=lambda i, t: MagicMock()):
            view = _make_view()
            view.set_plan(["step A", "step B", "step C"])
            self.assertEqual(len(view._steps), 3)

    def test_set_plan_empty_list(self):
        view = _make_view()
        view.set_plan([])
        self.assertEqual(len(view._steps), 0)

    def test_set_plan_replaces_previous(self):
        import rikugan.ui.plan_view as pv
        with unittest.mock.patch.object(pv, "PlanStepWidget", side_effect=lambda i, t: MagicMock()):
            view = _make_view()
            existing = MagicMock()
            view._steps = [existing]
            view.set_plan(["new step"])
            existing.deleteLater.assert_called_once()
            self.assertEqual(len(view._steps), 1)

    def test_set_plan_adds_widgets_to_container(self):
        import rikugan.ui.plan_view as pv
        with unittest.mock.patch.object(pv, "PlanStepWidget", side_effect=lambda i, t: MagicMock()):
            view = _make_view()
            view.set_plan(["a", "b"])
            self.assertEqual(view._steps_container.addWidget.call_count, 2)


# ---------------------------------------------------------------------------
# PlanView.set_step_status
# ---------------------------------------------------------------------------

class TestSetStepStatus(unittest.TestCase):
    def test_sets_status_on_valid_index(self):
        view = _make_view()
        mock_step = MagicMock()
        view._steps = [mock_step]
        view.set_step_status(0, "done")
        mock_step.set_status.assert_called_once_with("done")

    def test_ignores_out_of_bounds_high(self):
        view = _make_view()
        mock_step = MagicMock()
        view._steps = [mock_step]
        view.set_step_status(5, "done")  # must not raise
        mock_step.set_status.assert_not_called()

    def test_ignores_negative_index(self):
        view = _make_view()
        mock_step = MagicMock()
        view._steps = [mock_step]
        view.set_step_status(-1, "done")
        mock_step.set_status.assert_not_called()

    def test_empty_steps_list_noop(self):
        view = _make_view()
        view.set_step_status(0, "done")  # must not raise


# ---------------------------------------------------------------------------
# PlanView.set_buttons_visible
# ---------------------------------------------------------------------------

class TestSetButtonsVisible(unittest.TestCase):
    def test_shows_buttons(self):
        view = _make_view()
        view.set_buttons_visible(True)
        view._approve_btn.setVisible.assert_called_with(True)
        view._reject_btn.setVisible.assert_called_with(True)

    def test_hides_buttons(self):
        view = _make_view()
        view.set_buttons_visible(False)
        view._approve_btn.setVisible.assert_called_with(False)
        view._reject_btn.setVisible.assert_called_with(False)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

class TestCallbacks(unittest.TestCase):
    def test_fire_approved_calls_callback(self):
        view = _make_view()
        cb = MagicMock()
        view.set_approved_callback(cb)
        view._fire_approved()
        cb.assert_called_once()

    def test_fire_rejected_calls_callback(self):
        view = _make_view()
        cb = MagicMock()
        view.set_rejected_callback(cb)
        view._fire_rejected()
        cb.assert_called_once()

    def test_fire_approved_noop_when_no_callback(self):
        view = _make_view()
        view._fire_approved()  # must not raise

    def test_fire_rejected_noop_when_no_callback(self):
        view = _make_view()
        view._fire_rejected()  # must not raise

    def test_set_callback_replaces_previous(self):
        view = _make_view()
        cb1 = MagicMock()
        cb2 = MagicMock()
        view.set_approved_callback(cb1)
        view.set_approved_callback(cb2)
        view._fire_approved()
        cb1.assert_not_called()
        cb2.assert_called_once()


# ---------------------------------------------------------------------------
# PlanView.clear
# ---------------------------------------------------------------------------

class TestPlanViewClear(unittest.TestCase):
    def test_clear_removes_all_steps(self):
        view = _make_view()
        steps = [MagicMock(), MagicMock()]
        view._steps = list(steps)
        view.clear()
        self.assertEqual(len(view._steps), 0)

    def test_clear_calls_delete_later(self):
        view = _make_view()
        steps = [MagicMock(), MagicMock()]
        view._steps = list(steps)
        view.clear()
        for s in steps:
            s.deleteLater.assert_called_once()

    def test_clear_empty_noop(self):
        view = _make_view()
        view.clear()  # must not raise


if __name__ == "__main__":
    unittest.main()
