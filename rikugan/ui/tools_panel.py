"""Tools panel: container for bulk renamer, agent tree, and A2A bridge."""

from __future__ import annotations

from .qt_compat import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_HEADER_STYLE = "color: #d4d4d4; font-weight: bold; font-size: 12px;"

_PANEL_STYLE = """
    QFrame#tools_panel {
        background: #1e1e1e;
        border-left: 1px solid #3c3c3c;
    }
    QTabWidget::pane {
        border: none;
        background: #1e1e1e;
    }
    QTabBar::tab {
        background: #2d2d2d;
        color: #808080;
        border: 1px solid #3c3c3c;
        border-bottom: none;
        padding: 5px 14px;
        font-size: 11px;
        min-width: 60px;
    }
    QTabBar::tab:selected {
        background: #1e1e1e;
        color: #d4d4d4;
        border-bottom: 2px solid #4ec9b0;
    }
    QTabBar::tab:hover:!selected {
        background: #353535;
        color: #d4d4d4;
    }
"""


class ToolsPanel(QFrame):
    """Side panel containing tools tabs: Renamer, Agents, A2A."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("tools_panel")
        self.setStyleSheet(_PANEL_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("tools_panel_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Tools")
        title.setStyleSheet(_HEADER_STYLE)
        header_layout.addWidget(title)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setObjectName("tools_tabs")

        # Placeholder tabs
        self._renamer_placeholder = QLabel("Not loaded")
        self._renamer_placeholder.setStyleSheet("color: #808080; padding: 20px;")
        self._renamer_placeholder.setWordWrap(True)
        self._tabs.addTab(self._renamer_placeholder, "Renamer")

        self._agents_placeholder = QLabel("Not loaded")
        self._agents_placeholder.setStyleSheet("color: #808080; padding: 20px;")
        self._agents_placeholder.setWordWrap(True)
        self._tabs.addTab(self._agents_placeholder, "Agents")

        self._a2a_placeholder = QLabel("Not loaded")
        self._a2a_placeholder.setStyleSheet("color: #808080; padding: 20px;")
        self._a2a_placeholder.setWordWrap(True)
        self._tabs.addTab(self._a2a_placeholder, "A2A")

        main_layout.addWidget(self._tabs)

    def _replace_tab(self, index: int, widget: QWidget, label: str) -> None:
        """Replace the widget at the given tab index."""
        old = self._tabs.widget(index)
        self._tabs.removeTab(index)
        self._tabs.insertTab(index, widget, label)
        if old is not None:
            old.deleteLater()

    def set_renamer_widget(self, widget: QWidget) -> None:
        """Replace the Renamer tab content."""
        self._replace_tab(0, widget, "Renamer")

    def set_agents_widget(self, widget: QWidget) -> None:
        """Replace the Agents tab content."""
        self._replace_tab(1, widget, "Agents")

    def set_a2a_widget(self, widget: QWidget) -> None:
        """Replace the A2A tab content."""
        self._replace_tab(2, widget, "A2A")
