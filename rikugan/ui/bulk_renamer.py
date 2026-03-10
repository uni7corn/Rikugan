"""Bulk function renaming UI for the Renamer tab."""

from __future__ import annotations

from dataclasses import dataclass

from .qt_compat import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    Signal,
)

_BTN_STYLE = (
    "QPushButton { background: #2d2d2d; color: #d4d4d4; border: 1px solid #3c3c3c; "
    "border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
    "QPushButton:hover { background: #3c3c3c; }"
    "QPushButton:disabled { color: #555; }"
)

_TABLE_STYLE = """
    QTableWidget {
        background: #1e1e1e;
        color: #d4d4d4;
        border: 1px solid #3c3c3c;
        gridline-color: #3c3c3c;
        font-size: 11px;
        alternate-background-color: #252525;
    }
    QTableWidget::item {
        padding: 2px 4px;
    }
    QTableWidget::item:selected {
        background: #2d2d2d;
    }
    QHeaderView::section {
        background: #2d2d2d;
        color: #d4d4d4;
        border: 1px solid #3c3c3c;
        padding: 3px 6px;
        font-size: 10px;
    }
"""

_FILTER_STYLE = (
    "QLineEdit { background: #2d2d2d; color: #d4d4d4; border: 1px solid #3c3c3c; "
    "border-radius: 3px; padding: 3px 6px; font-size: 11px; }"
    "QLineEdit:focus { border-color: #4ec9b0; }"
)

_COMBO_STYLE = (
    "QComboBox { background: #2d2d2d; color: #d4d4d4; border: 1px solid #3c3c3c; "
    "border-radius: 3px; padding: 3px 6px; font-size: 11px; }"
)

_SPIN_STYLE = (
    "QSpinBox { background: #2d2d2d; color: #d4d4d4; border: 1px solid #3c3c3c; "
    "border-radius: 3px; padding: 2px 4px; font-size: 11px; }"
)

_PROGRESS_STYLE = (
    "QProgressBar { background: #2d2d2d; border: 1px solid #3c3c3c; "
    "border-radius: 3px; text-align: center; color: #d4d4d4; font-size: 10px; }"
    "QProgressBar::chunk { background: #4ec9b0; border-radius: 2px; }"
)

_RADIO_STYLE = "QRadioButton { color: #d4d4d4; font-size: 11px; spacing: 4px; }"

_STATUS_COLORS: dict[str, str] = {
    "queued": "#808080",
    "analyzing": "#dcdcaa",
    "renamed": "#4ec9b0",
    "skipped": "#d7ba7d",
    "error": "#f44747",
}

# Column indices
_COL_CHECK = 0
_COL_ADDR = 1
_COL_NAME = 2
_COL_NEWNAME = 3
_COL_STATUS = 4


@dataclass
class FunctionEntry:
    """A function loaded into the renamer table."""

    address: int
    name: str
    is_import: bool
    instruction_count: int


class BulkRenamerWidget(QWidget):
    """Bulk function renaming interface with filtering and batch controls."""

    start_requested = Signal(list, str, int, int)  # jobs, mode, batch_size, max_concurrent
    pause_requested = Signal()
    cancel_requested = Signal()
    undo_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("bulk_renamer_widget")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # --- Top bar: filter + selection controls ---
        top_bar = QHBoxLayout()
        top_bar.setSpacing(4)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter functions...")
        self._filter_edit.setStyleSheet(_FILTER_STYLE)
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        top_bar.addWidget(self._filter_edit, 1)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setStyleSheet(_BTN_STYLE)
        self._select_all_btn.clicked.connect(self._on_select_all)
        top_bar.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.setStyleSheet(_BTN_STYLE)
        self._deselect_all_btn.clicked.connect(self._on_deselect_all)
        top_bar.addWidget(self._deselect_all_btn)

        self._filter_combo = QComboBox()
        self._filter_combo.setStyleSheet(_COMBO_STYLE)
        self._filter_combo.addItems(["All Functions", "Auto-named Only", "User-renamed", "Imports"])
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        top_bar.addWidget(self._filter_combo)

        self._selection_label = QLabel("0 / 0 selected")
        self._selection_label.setStyleSheet("color: #808080; font-size: 11px;")
        top_bar.addWidget(self._selection_label)

        main_layout.addLayout(top_bar)

        # --- Table ---
        self._table = QTableWidget()
        self._table.setObjectName("renamer_table")
        self._table.setStyleSheet(_TABLE_STYLE)
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["", "Address", "Current Name", "New Name", "Status"])
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(4, 80)

        self._table.itemChanged.connect(self._on_item_changed)
        main_layout.addWidget(self._table)

        # --- Analysis controls ---
        analysis_bar = QHBoxLayout()
        analysis_bar.setSpacing(6)

        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        analysis_bar.addWidget(mode_label)

        self._quick_radio = QRadioButton("Quick")
        self._quick_radio.setStyleSheet(_RADIO_STYLE)
        self._quick_radio.setChecked(True)
        analysis_bar.addWidget(self._quick_radio)

        self._deep_radio = QRadioButton("Deep")
        self._deep_radio.setStyleSheet(_RADIO_STYLE)
        analysis_bar.addWidget(self._deep_radio)

        analysis_bar.addSpacing(12)

        batch_label = QLabel("Batch:")
        batch_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        analysis_bar.addWidget(batch_label)

        self._batch_spin = QSpinBox()
        self._batch_spin.setStyleSheet(_SPIN_STYLE)
        self._batch_spin.setRange(1, 50)
        self._batch_spin.setValue(10)
        self._batch_spin.setFixedWidth(60)
        analysis_bar.addWidget(self._batch_spin)

        concurrent_label = QLabel("Concurrent:")
        concurrent_label.setStyleSheet("color: #d4d4d4; font-size: 11px;")
        analysis_bar.addWidget(concurrent_label)

        self._concurrent_spin = QSpinBox()
        self._concurrent_spin.setStyleSheet(_SPIN_STYLE)
        self._concurrent_spin.setRange(1, 10)
        self._concurrent_spin.setValue(3)
        self._concurrent_spin.setFixedWidth(60)
        analysis_bar.addWidget(self._concurrent_spin)

        analysis_bar.addStretch()
        main_layout.addLayout(analysis_bar)

        # --- Action bar ---
        action_bar = QHBoxLayout()
        action_bar.setSpacing(4)

        self._start_btn = QPushButton("Start")
        self._start_btn.setStyleSheet(
            "QPushButton { background: #2d2d2d; color: #4ec9b0; border: 1px solid #4ec9b0; "
            "border-radius: 4px; padding: 4px 14px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: #3c3c3c; }"
            "QPushButton:disabled { color: #555; border-color: #555; }"
        )
        self._start_btn.clicked.connect(self._on_start)
        action_bar.addWidget(self._start_btn)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setStyleSheet(_BTN_STYLE)
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self.pause_requested.emit)
        action_bar.addWidget(self._pause_btn)

        self._undo_btn = QPushButton("Undo All")
        self._undo_btn.setStyleSheet(_BTN_STYLE)
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.undo_requested.emit)
        action_bar.addWidget(self._undo_btn)

        self._progress = QProgressBar()
        self._progress.setStyleSheet(_PROGRESS_STYLE)
        self._progress.setFixedHeight(18)
        self._progress.setValue(0)
        action_bar.addWidget(self._progress, 1)

        self._progress_label = QLabel("0 / 0")
        self._progress_label.setStyleSheet("color: #808080; font-size: 11px;")
        action_bar.addWidget(self._progress_label)

        main_layout.addLayout(action_bar)

        # Internal state
        self._entries: list[FunctionEntry] = []
        self._row_map: dict[int, int] = {}  # address -> row index

    def load_functions(self, functions: list[dict]) -> None:
        """Populate the table from a list of function dicts.

        Each dict: {"address": int, "name": str, "is_import": bool, "instruction_count": int}
        """
        self._table.itemChanged.disconnect(self._on_item_changed)
        self._table.setRowCount(0)
        self._entries.clear()
        self._row_map.clear()

        self._table.setRowCount(len(functions))

        for row, func in enumerate(functions):
            entry = FunctionEntry(
                address=func["address"],
                name=func["name"],
                is_import=func.get("is_import", False),
                instruction_count=func.get("instruction_count", 0),
            )
            self._entries.append(entry)
            self._row_map[entry.address] = row

            # Checkbox column
            check_item = QTableWidgetItem()
            # Heuristic: pre-select auto-named functions (sub_, fn_, loc_)
            is_auto = self._is_auto_named(entry.name)
            check_item.setCheckState(
                Qt.CheckState.Checked if (is_auto and not entry.is_import) else Qt.CheckState.Unchecked
            )
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row, _COL_CHECK, check_item)

            # Address
            addr_item = QTableWidgetItem(f"0x{entry.address:X}")
            addr_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            addr_item.setToolTip(f"0x{entry.address:016X}")
            self._table.setItem(row, _COL_ADDR, addr_item)

            # Current name
            name_item = QTableWidgetItem(entry.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, _COL_NAME, name_item)

            # New name (initially empty)
            new_item = QTableWidgetItem("")
            new_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, _COL_NEWNAME, new_item)

            # Status
            status_item = QTableWidgetItem("")
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, _COL_STATUS, status_item)

        self._table.itemChanged.connect(self._on_item_changed)
        self._update_selection_count()

    def update_job(self, address: int, new_name: str, status: str, error: str) -> None:
        """Update a row by address with new name, status, and optional error."""
        row = self._row_map.get(address)
        if row is None:
            return

        if new_name:
            new_item = self._table.item(row, _COL_NEWNAME)
            if new_item:
                new_item.setText(new_name)

        status_item = self._table.item(row, _COL_STATUS)
        if status_item:
            display = error if error else status
            status_item.setText(display)
            color = _STATUS_COLORS.get(status, "#d4d4d4")
            from .qt_compat import QColor

            status_item.setForeground(QColor(color))

    def set_progress(self, current: int, total: int) -> None:
        """Update the progress bar and label."""
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(current)
        else:
            self._progress.setMaximum(1)
            self._progress.setValue(0)
        self._progress_label.setText(f"{current} / {total}")

        # Enable undo if any work has been done
        self._undo_btn.setEnabled(current > 0)

        # Toggle pause/start based on completion
        if current >= total and total > 0:
            self._start_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)

    def _on_filter_changed(self) -> None:
        """Filter table rows based on text filter and combo selection."""
        text = self._filter_edit.text().strip().lower()
        combo_idx = self._filter_combo.currentIndex()

        for row in range(self._table.rowCount()):
            if row >= len(self._entries):
                break
            entry = self._entries[row]
            name = entry.name.lower()

            # Text filter
            text_match = not text or text in name or text in f"0x{entry.address:x}"

            # Combo filter
            combo_match = True
            if combo_idx == 1:  # Auto-named Only
                combo_match = self._is_auto_named(entry.name)
            elif combo_idx == 2:  # User-renamed
                combo_match = not self._is_auto_named(entry.name) and not entry.is_import
            elif combo_idx == 3:  # Imports
                combo_match = entry.is_import

            self._table.setRowHidden(row, not (text_match and combo_match))

    def _on_select_all(self) -> None:
        """Check all visible rows."""
        self._table.itemChanged.disconnect(self._on_item_changed)
        for row in range(self._table.rowCount()):
            if not self._table.isRowHidden(row):
                item = self._table.item(row, _COL_CHECK)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)
        self._table.itemChanged.connect(self._on_item_changed)
        self._update_selection_count()

    def _on_deselect_all(self) -> None:
        """Uncheck all rows."""
        self._table.itemChanged.disconnect(self._on_item_changed)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COL_CHECK)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._table.itemChanged.connect(self._on_item_changed)
        self._update_selection_count()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Track checkbox state changes."""
        if item.column() == _COL_CHECK:
            self._update_selection_count()

    def _get_selected_jobs(self) -> list[dict]:
        """Return list of dicts with address and current_name for checked rows."""
        jobs = []
        for row in range(self._table.rowCount()):
            check_item = self._table.item(row, _COL_CHECK)
            if check_item and check_item.checkState() == Qt.CheckState.Checked:
                if row < len(self._entries):
                    entry = self._entries[row]
                    jobs.append(
                        {
                            "address": entry.address,
                            "current_name": entry.name,
                        }
                    )
        return jobs

    def _on_start(self) -> None:
        """Collect selected functions and emit start_requested."""
        jobs = self._get_selected_jobs()
        if not jobs:
            return
        mode = "deep" if self._deep_radio.isChecked() else "quick"
        batch_size = self._batch_spin.value()
        max_concurrent = self._concurrent_spin.value()

        self._start_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)

        # Mark selected jobs as queued
        for job in jobs:
            self.update_job(job["address"], "", "queued", "")

        self.set_progress(0, len(jobs))
        self.start_requested.emit(jobs, mode, batch_size, max_concurrent)

    def _update_selection_count(self) -> None:
        """Update the selection count label."""
        total = self._table.rowCount()
        selected = 0
        for row in range(total):
            item = self._table.item(row, _COL_CHECK)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected += 1
        self._selection_label.setText(f"{selected} / {total} selected")

    @staticmethod
    def _is_auto_named(name: str) -> bool:
        """Heuristic: detect auto-generated function names."""
        prefixes = ("sub_", "fn_", "loc_", "j_", "nullsub_", "unknown_", "FUN_")
        return name.startswith(prefixes)
