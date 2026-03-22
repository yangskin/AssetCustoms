"""FR4 分诊 UI（Triage UI）：检查链失败时弹出的 PySide6 窗口。

职责：
- 展示 CheckResult.failures（红色错误标题 + 详细原因）
- 展示贴图映射表（已匹配项预填、未匹配项下拉选择孤儿贴图）
- Base_Name 文本框（可编辑）
- "执行标准化" / "取消并保留隔离区" 按钮
- 用户确认后回调执行 FR5 引擎
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.pipeline.check_chain import CheckFailure, CheckResult
from core.textures.matcher import MatchResult


# ---------------------------------------------------------------------------
# 数据模型：分诊结果
# ---------------------------------------------------------------------------

@dataclass
class TriageDecision:
    """用户在分诊 UI 中做出的决定。"""
    accepted: bool = False
    corrected_mapping: Dict[str, str] = field(default_factory=dict)
    base_name: str = ""


# ---------------------------------------------------------------------------
# 样式常量
# ---------------------------------------------------------------------------

_UE_DARK = "#1a1a1a"
_UE_MID = "#2a2a2a"
_UE_LIGHT = "#3a3a3a"
_UE_TEXT = "#c0c0c0"
_UE_ACCENT = "#0078d4"
_UE_RED = "#e04040"
_UE_GREEN = "#40b040"


_STYLESHEET = f"""
QWidget {{
    background-color: {_UE_DARK};
    color: {_UE_TEXT};
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {_UE_LIGHT};
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}
QTableWidget {{
    background-color: {_UE_MID};
    gridline-color: {_UE_LIGHT};
    selection-background-color: {_UE_ACCENT};
    border: 1px solid {_UE_LIGHT};
}}
QTableWidget::item {{
    padding: 6px 8px;
}}
QHeaderView::section {{
    background-color: {_UE_LIGHT};
    color: {_UE_TEXT};
    padding: 6px 10px;
    border: none;
    font-weight: bold;
}}
QComboBox {{
    background-color: {_UE_MID};
    border: 1px solid {_UE_LIGHT};
    padding: 4px 10px;
    border-radius: 2px;
    min-height: 24px;
}}
QComboBox::drop-down {{
    border: none;
}}
QLineEdit {{
    background-color: {_UE_MID};
    border: 1px solid {_UE_LIGHT};
    padding: 4px 8px;
    border-radius: 2px;
}}
QPushButton {{
    background-color: {_UE_LIGHT};
    border: 1px solid #555;
    padding: 6px 16px;
    border-radius: 3px;
    min-width: 80px;
}}
QPushButton:hover {{
    background-color: #444;
}}
QPushButton#btn_execute {{
    background-color: {_UE_ACCENT};
    color: white;
    font-weight: bold;
}}
QPushButton#btn_execute:hover {{
    background-color: #1a8ae6;
}}
QPushButton#btn_execute:disabled {{
    background-color: #555;
    color: #888;
}}
"""


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------

class TriageWindow(QtWidgets.QWidget):
    """FR4 分诊 UI 主窗口。

    Args:
        check_result: FR3 检查链的输出。
        base_name: 从 FBX 文件名提取的基础名。
        all_texture_paths: 统一贴图清单（外部 + 嵌入伪路径）。
        on_accept: 用户确认后的回调，传入 TriageDecision。
        on_cancel: 用户取消的回调。
    """

    def __init__(
        self,
        check_result: CheckResult,
        base_name: str,
        all_texture_paths: List[str],
        on_accept: Optional[Callable[[TriageDecision], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._check_result = check_result
        self._base_name = base_name
        self._all_texture_paths = sorted(all_texture_paths)
        self._on_accept = on_accept
        self._on_cancel = on_cancel
        self._slot_combos: Dict[str, QtWidgets.QComboBox] = {}

        self.setWindowTitle("AssetCustoms — 分诊 (Triage)")
        self.setMinimumSize(680, 480)
        self.setStyleSheet(_STYLESHEET)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # --- 1. 错误标题 ---
        root.addWidget(self._build_error_header())

        # --- 2. Base Name ---
        root.addWidget(self._build_name_section())

        # --- 3. 贴图映射表 ---
        root.addWidget(self._build_mapping_section(), stretch=1)

        # --- 4. 按钮栏 ---
        root.addLayout(self._build_buttons())

    def _build_error_header(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("检查失败原因")
        layout = QtWidgets.QVBoxLayout(group)
        for f in self._check_result.failures:
            label = QtWidgets.QLabel(f"  ✖  [{f.check_name}] {f.reason}")
            label.setStyleSheet(f"color: {_UE_RED}; font-weight: bold;")
            label.setWordWrap(True)
            layout.addWidget(label)
        return group

    def _build_name_section(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("资产基础名")
        layout = QtWidgets.QHBoxLayout(group)
        layout.addWidget(QtWidgets.QLabel("Base Name:"))
        self._name_edit = QtWidgets.QLineEdit(self._base_name)
        layout.addWidget(self._name_edit, stretch=1)
        return group

    def _build_mapping_section(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("贴图映射 (Texture Mapping)")
        layout = QtWidgets.QVBoxLayout(group)

        mr = self._check_result.match_result
        if mr is None:
            layout.addWidget(QtWidgets.QLabel("无匹配信息。"))
            return group

        # 收集所有逻辑位（已映射 + 未映射 + 歧义）
        all_slots = set(mr.mapping.keys()) | set(mr.unmapped_slots) | set(mr.ambiguous_slots)
        if mr.candidates:
            all_slots |= set(mr.candidates.keys())

        sorted_slots = sorted(all_slots)

        # 构建表格
        table = QtWidgets.QTableWidget(len(sorted_slots), 3)
        table.setHorizontalHeaderLabels(["逻辑位 (Slot)", "状态", "贴图选择"])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().resizeSection(1, 100)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)

        # 候选列表 = 已映射文件 + 孤儿文件 + 所有文件
        candidate_display = ["(未选择)"] + [self._display_name(p) for p in self._all_texture_paths]
        candidate_values = [""] + list(self._all_texture_paths)

        for row, slot in enumerate(sorted_slots):
            # 列 0：逻辑位名
            slot_item = QtWidgets.QTableWidgetItem(slot)
            slot_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 0, slot_item)

            # 列 1：状态标记
            current_file = mr.mapping.get(slot, "")
            if slot in mr.ambiguous_slots:
                status = "⚠ 歧义"
                color = "#e0a030"
            elif current_file:
                status = "✔ 已匹配"
                color = _UE_GREEN
            else:
                status = "✖ 未匹配"
                color = _UE_RED

            status_item = QtWidgets.QTableWidgetItem(status)
            status_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            status_item.setForeground(QtGui.QColor(color))
            table.setItem(row, 1, status_item)

            # 列 2：下拉选择框
            combo = QtWidgets.QComboBox()
            for i, display in enumerate(candidate_display):
                combo.addItem(display, candidate_values[i])

            # 预选当前映射
            if current_file and current_file in candidate_values:
                combo.setCurrentIndex(candidate_values.index(current_file))

            table.setCellWidget(row, 2, combo)
            self._slot_combos[slot] = combo

        for r in range(table.rowCount()):
            table.setRowHeight(r, 36)
        layout.addWidget(table)

        # 孤儿信息
        if mr.orphans:
            orphan_label = QtWidgets.QLabel(
                f"孤儿贴图 ({len(mr.orphans)}): "
                + ", ".join(self._display_name(p) for p in mr.orphans)
            )
            orphan_label.setStyleSheet(f"color: #e0a030; font-style: italic;")
            orphan_label.setWordWrap(True)
            layout.addWidget(orphan_label)

        return group

    def _build_buttons(self) -> QtWidgets.QHBoxLayout:
        layout = QtWidgets.QHBoxLayout()
        layout.addStretch()

        btn_cancel = QtWidgets.QPushButton("取消 (保留隔离区)")
        btn_cancel.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(btn_cancel)

        btn_execute = QtWidgets.QPushButton("执行标准化")
        btn_execute.setObjectName("btn_execute")
        btn_execute.clicked.connect(self._on_execute_clicked)
        layout.addWidget(btn_execute)

        return layout

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_execute_clicked(self) -> None:
        decision = TriageDecision(
            accepted=True,
            corrected_mapping=self._collect_mapping(),
            base_name=self._name_edit.text().strip(),
        )
        self.close()
        if self._on_accept:
            self._on_accept(decision)

    def _on_cancel_clicked(self) -> None:
        self.close()
        if self._on_cancel:
            self._on_cancel()

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _collect_mapping(self) -> Dict[str, str]:
        """从 UI 下拉框收集用户修正后的映射。"""
        mapping: Dict[str, str] = {}
        for slot, combo in self._slot_combos.items():
            value = combo.currentData()
            if value:
                mapping[slot] = value
        return mapping

    @staticmethod
    def _display_name(path: str) -> str:
        """提取文件显示名（basename 或 UE 资产末段）。"""
        if "/" in path:
            return path.split("/")[-1]
        return os.path.basename(path)
