"""Tests for rikugan.ui.qt_compat — Qt compatibility shim."""

from __future__ import annotations

import importlib
import sys
import types
import unittest


def _build_pyside6_mock() -> None:
    """Inject a minimal PySide6 stub into sys.modules using subclassable classes."""

    def _stub_mod(name: str, **kw) -> types.ModuleType:
        mod = types.ModuleType(name)
        mod.__dict__.update(kw)
        return mod

    def _qt_class(class_name: str) -> type:
        return type(class_name, (), {"__init__": lambda self, *a, **k: None})

    class _Signal:
        def __init__(self, *a): pass
        def connect(self, *a): pass
        def disconnect(self, *a): pass
        def emit(self, *a): pass
        def __get__(self, obj, objtype=None): return self

    _sentinel = type("_Qt", (), {})()  # non-class sentinel for non-subclassed attrs

    qtwidget_names = [
        "QApplication", "QWidget", "QVBoxLayout", "QHBoxLayout", "QLabel",
        "QPushButton", "QPlainTextEdit", "QScrollArea", "QFrame", "QSplitter",
        "QDialog", "QDialogButtonBox", "QComboBox", "QLineEdit", "QSpinBox",
        "QDoubleSpinBox", "QCheckBox", "QGroupBox", "QFormLayout",
        "QToolButton", "QSizePolicy", "QTabWidget", "QTabBar",
        "QFileDialog", "QMenu", "QMessageBox",
    ]
    sys.modules.setdefault("PySide6", _stub_mod("PySide6"))
    sys.modules.setdefault(
        "PySide6.QtCore",
        _stub_mod("PySide6.QtCore", Signal=_Signal, Qt=_sentinel,
                  QObject=_qt_class("QObject"), QTimer=_qt_class("QTimer")),
    )
    sys.modules.setdefault(
        "PySide6.QtWidgets",
        _stub_mod("PySide6.QtWidgets", **{n: _qt_class(n) for n in qtwidget_names}),
    )


_build_pyside6_mock()
import rikugan.ui.qt_compat as qt_compat  # noqa: E402


class TestQtCompat(unittest.TestCase):
    def test_is_pyside6_returns_true(self):
        self.assertTrue(qt_compat.is_pyside6())

    def test_qt_binding_constant(self):
        self.assertEqual(qt_compat.QT_BINDING, "PySide6")

    def test_qt_core_symbols_exported(self):
        for name in ("Signal", "Qt", "QObject", "QTimer"):
            self.assertTrue(hasattr(qt_compat, name), f"missing {name}")
        self.assertTrue(qt_compat.is_pyside6())

    def test_qt_widget_symbols_exported(self):
        for name in (
            "QApplication", "QWidget", "QVBoxLayout", "QHBoxLayout",
            "QLabel", "QPushButton", "QPlainTextEdit", "QScrollArea",
            "QDialog", "QComboBox", "QLineEdit", "QCheckBox",
            "QMenu", "QMessageBox",
        ):
            self.assertTrue(hasattr(qt_compat, name), f"missing {name}")


if __name__ == "__main__":
    unittest.main()
