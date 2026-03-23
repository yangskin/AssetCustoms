"""AssetCustoms 图形化配置编辑器：PySide6 表单 GUI。

面向美术人员，无需手写 JSON — 通过下拉框、输入框、复选框等控件
可视化编辑 Content/Config/AssetCustoms/*.jsonc 配置文件。
支持：新建 / 选择 / 删除 / 读取 / 保存。
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

# ---------------------------------------------------------------------------
# JSONC 读写工具
# ---------------------------------------------------------------------------

def _load_jsonc(path: str) -> dict:
    from core.config.jsonc import load_jsonc_file
    return load_jsonc_file(path)


def _dict_to_jsonc(data: dict) -> str:
    """Serialize config dict to a well-commented JSONC string."""
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    lines = raw.split("\n")
    result: list[str] = []
    in_output_defs = False
    output_index = 0
    tod = data.get("texture_output_definitions", [])

    for line in lines:
        # Top-level key comments (exactly 2-space indent)
        if line.startswith('  "config_version"'):
            result.append("  // === AssetCustoms 配置 (JSONC) ===")
            result.append("  // 运行时占位符：{Name} {Suffix} {Category} {DropDir}")
        elif line.startswith('  "default_master_material_path"'):
            result.append("")
            result.append('  // 母材质路径（空 = 不创建材质实例）')
        elif line.startswith('  "default_fallback_import_path"'):
            result.append("  // 默认落地路径（当 target_path_template 计算失败时使用）")
        elif line.startswith('  "target_path_template"'):
            result.append("  // UE 资产落地目录模板（支持 {Category}, {Name} 等占位符）")
        elif line.startswith('  "conflict_policy"'):
            result.append("  // 命名冲突策略：overwrite | skip | version")
        elif line.startswith('  "asset_naming_template"'):
            result.append("")
            result.append("  // 资产命名模板（仅影响导入后的 UE 资产名）")
        elif line.startswith('  "texture_input_rules"'):
            result.append("")
            result.append("  // === 输入识别规则（从投放目录匹配文件到逻辑位） ===")
        elif line.startswith('  "texture_output_definitions"'):
            result.append("")
            result.append("  // === 输出贴图定义（通道编排 + UE 导入属性） ===")
            if not line.strip().endswith("[]"):
                in_output_defs = True
                output_index = 0

        # Per-output definition comment
        if in_output_defs and line == "    {":
            if output_index < len(tod):
                name = tod[output_index].get("output_name", f"Output {output_index + 1}")
                result.append(f"    // --- {name} ---")
                output_index += 1

        if in_output_defs and line.rstrip().rstrip(",") == "  ]":
            in_output_defs = False

        result.append(line)

    return "\n".join(result) + "\n"


def _save_jsonc(path: str, data: dict) -> None:
    """Save config dict as a .jsonc file with section comments."""
    text = _dict_to_jsonc(data)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# 禁用滚轮的控件子类（防止美术误操作）
# ---------------------------------------------------------------------------

class NoScrollComboBox(QtWidgets.QComboBox):
    """QComboBox that ignores wheel events to prevent accidental changes."""
    def wheelEvent(self, event: QtCore.QEvent) -> None:
        event.ignore()


class NoScrollSpinBox(QtWidgets.QSpinBox):
    """QSpinBox: no wheel, no buttons (pure input)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)

    def wheelEvent(self, event: QtCore.QEvent) -> None:
        event.ignore()


class NoScrollDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """QDoubleSpinBox: no wheel, no buttons (pure input)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)

    def wheelEvent(self, event: QtCore.QEvent) -> None:
        event.ignore()


# ---------------------------------------------------------------------------
# 常量选项（Schema 中的枚举值）
# ---------------------------------------------------------------------------

CONFLICT_POLICIES = ["overwrite", "skip", "version"]
MATCH_MODES = ["glob", "regex"]
FILE_FORMATS = ["PNG", "TGA", "EXR"]
BIT_DEPTHS = [8, 16, 32]
COMPRESSIONS = [
    "TC_Default", "TC_Normalmap", "TC_Masks", "TC_Grayscale",
    "TC_Displacementmap", "TC_VectorDisplacementmap", "TC_HDR",
    "TC_EditorIcon", "TC_Alpha", "TC_DistanceFieldFont",
    "TC_HDR_Compressed", "TC_BC7", "TC_HalfFloat",
]
LOD_GROUPS = [
    "TEXTUREGROUP_World", "TEXTUREGROUP_WorldNormalMap",
    "TEXTUREGROUP_WorldSpecular",
    "TEXTUREGROUP_Character", "TEXTUREGROUP_CharacterNormalMap",
    "TEXTUREGROUP_CharacterSpecular",
    "TEXTUREGROUP_Weapon", "TEXTUREGROUP_WeaponNormalMap",
    "TEXTUREGROUP_WeaponSpecular",
    "TEXTUREGROUP_Vehicle", "TEXTUREGROUP_VehicleNormalMap",
    "TEXTUREGROUP_VehicleSpecular",
    "TEXTUREGROUP_UI",
    "TEXTUREGROUP_Effects", "TEXTUREGROUP_EffectsNotFiltered",
    "TEXTUREGROUP_Lightmap", "TEXTUREGROUP_Shadowmap",
    "TEXTUREGROUP_RenderTarget",
    "TEXTUREGROUP_Pixels2D",
]
ADDRESS_MODES = ["Wrap", "Clamp", "Mirror"]
MIP_GEN_MODES = ["FromTextureGroup", "SimpleAverage", "Sharpen0", "Sharpen1",
                  "Sharpen2", "NoMipmaps"]
NORMAL_SPACES = ["", "OpenGL", "DirectX"]
CHANNEL_NAMES = ["R", "G", "B", "A"]
# 常见逻辑源名
COMMON_SOURCES = [
    "", "BaseColor", "Normal", "Roughness", "Metallic",
    "AmbientOcclusion", "Height", "Opacity", "SubsurfaceColor",
    "Emissive", "Specular",
]

# ---------------------------------------------------------------------------
# 深色主题样式表
# ---------------------------------------------------------------------------

DARK_STYLE = """
QWidget { background-color: #2B2B2B; color: #D4D4D4; font-size: 12px; }
QScrollArea { border: none; }
QGroupBox { border: 1px solid #444; border-radius: 4px; margin-top: 8px;
            padding-top: 14px; font-weight: bold; color: #E0E0E0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #3C3C3C; border: 1px solid #555; border-radius: 3px;
    padding: 3px 6px; color: #D4D4D4; min-height: 22px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #0078D4; }
QComboBox::drop-down {
    subcontrol-origin: padding; subcontrol-position: right center;
    width: 20px; border-left: 1px solid #555; background: transparent; }
QComboBox::down-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid #D4D4D4; }
QComboBox QAbstractItemView { background: #3C3C3C; color: #D4D4D4;
    selection-background-color: #094771; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QPushButton { background-color: #0E639C; color: white; border: none;
              padding: 5px 14px; border-radius: 3px; min-height: 24px; }
QPushButton:hover { background-color: #1177BB; }
QPushButton:pressed { background-color: #094771; }
QPushButton[danger="true"] { background-color: #A1260D; }
QPushButton[danger="true"]:hover { background-color: #C4260D; }
QPushButton[secondary="true"] { background-color: #3C3C3C; border: 1px solid #555; }
QPushButton[secondary="true"]:hover { background-color: #505050; }
QLabel { background: transparent; }
QTabWidget::pane { border: 1px solid #444; top: -1px; }
QTabBar::tab { background: #2B2B2B; border: 1px solid #444; padding: 6px 16px;
               margin-right: 2px; border-bottom: none; border-top-left-radius: 4px;
               border-top-right-radius: 4px; }
QTabBar::tab:selected { background: #3C3C3C; border-bottom-color: #3C3C3C; }
QTabBar::tab:hover { background: #353535; }
QListWidget { background-color: #2B2B2B; border: 1px solid #444; }
QListWidget::item:selected { background-color: #094771; }
QListWidget::item:hover { background-color: #353535; }
"""


# ===========================================================================
# 辅助控件
# ===========================================================================

class LabeledLine(QtWidgets.QWidget):
    """标签 + 文本输入。"""
    def __init__(self, label: str, value: str = "", tooltip: str = "", parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(160)
        lbl.setToolTip(tooltip)
        self.edit = QtWidgets.QLineEdit(value)
        self.edit.setToolTip(tooltip)
        lay.addWidget(lbl)
        lay.addWidget(self.edit, 1)

    def value(self) -> str:
        return self.edit.text()

    def set_value(self, v: str) -> None:
        self.edit.setText(v)


class LabeledCombo(QtWidgets.QWidget):
    """标签 + 下拉框。"""
    def __init__(self, label: str, items: list[str], current: str = "",
                 tooltip: str = "", editable: bool = False, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(160)
        lbl.setToolTip(tooltip)
        self.combo = NoScrollComboBox()
        self.combo.setEditable(editable)
        self.combo.addItems(items)
        self.combo.setToolTip(tooltip)
        if current in items:
            self.combo.setCurrentText(current)
        elif editable and current:
            self.combo.setCurrentText(current)
        lay.addWidget(lbl)
        lay.addWidget(self.combo, 1)

    def value(self) -> str:
        return self.combo.currentText()

    def set_value(self, v: str) -> None:
        self.combo.setCurrentText(v)


class LabeledCheck(QtWidgets.QWidget):
    """标签 + 复选框。"""
    def __init__(self, label: str, checked: bool = False, tooltip: str = "", parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.check = QtWidgets.QCheckBox(label)
        self.check.setChecked(checked)
        self.check.setToolTip(tooltip)
        lay.addWidget(self.check)

    def value(self) -> bool:
        return self.check.isChecked()

    def set_value(self, v: bool) -> None:
        self.check.setChecked(v)


class LabeledSpin(QtWidgets.QWidget):
    """标签 + 整数自旋框。"""
    def __init__(self, label: str, value: int = 0, minimum: int = 0,
                 maximum: int = 99999, tooltip: str = "", parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(160)
        lbl.setToolTip(tooltip)
        self.spin = NoScrollSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value)
        self.spin.setToolTip(tooltip)
        lay.addWidget(lbl)
        lay.addWidget(self.spin, 1)

    def value(self) -> int:
        return self.spin.value()

    def set_value(self, v: int) -> None:
        self.spin.setValue(v)


class LabeledFloat(QtWidgets.QWidget):
    """标签 + 浮点自旋框。"""
    def __init__(self, label: str, value: float = 0.0, minimum: float = 0.0,
                 maximum: float = 1.0, decimals: int = 2, tooltip: str = "", parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(160)
        lbl.setToolTip(tooltip)
        self.spin = NoScrollDoubleSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setDecimals(decimals)
        self.spin.setValue(value)
        self.spin.setToolTip(tooltip)
        lay.addWidget(lbl)
        lay.addWidget(self.spin, 1)

    def value(self) -> float:
        return self.spin.value()

    def set_value(self, v: float) -> None:
        self.spin.setValue(v)


class EditableListWidget(QtWidgets.QWidget):
    """可增删的字符串列表编辑控件。"""
    def __init__(self, label: str, items: list[str] | None = None,
                 tooltip: str = "", parent=None):
        super().__init__(parent)
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(2)
        lbl = QtWidgets.QLabel(label)
        lbl.setToolTip(tooltip)
        main.addWidget(lbl)

        row = QtWidgets.QHBoxLayout()
        self._list = QtWidgets.QListWidget()
        self._list.setMaximumHeight(90)
        if items:
            self._list.addItems(items)
        row.addWidget(self._list, 1)

        btns = QtWidgets.QVBoxLayout()
        self._btn_add = QtWidgets.QPushButton("+")
        self._btn_add.setFixedSize(28, 28)
        self._btn_add.setProperty("secondary", True)
        self._btn_add.clicked.connect(self._on_add)
        self._btn_del = QtWidgets.QPushButton("−")
        self._btn_del.setFixedSize(28, 28)
        self._btn_del.setProperty("danger", True)
        self._btn_del.clicked.connect(self._on_del)
        btns.addWidget(self._btn_add)
        btns.addWidget(self._btn_del)
        btns.addStretch()
        row.addLayout(btns)
        main.addLayout(row)

    def _on_add(self) -> None:
        text, ok = QtWidgets.QInputDialog.getText(self, "Add Item", "Value:")
        if ok and text.strip():
            self._list.addItem(text.strip())

    def _on_del(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def values(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def set_values(self, items: list[str]) -> None:
        self._list.clear()
        self._list.addItems(items)


# ===========================================================================
# 通道编辑控件（ChannelDef 的一行）
# ===========================================================================

class ChannelDefRow(QtWidgets.QWidget):
    """单个通道（R/G/B/A）的编辑行。"""
    def __init__(self, channel_label: str, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        lbl = QtWidgets.QLabel(channel_label)
        lbl.setFixedWidth(20)
        lbl.setStyleSheet("font-weight: bold;")
        lay.addWidget(lbl)

        lay.addWidget(QtWidgets.QLabel("Source:"))
        self.cb_source = NoScrollComboBox()
        self.cb_source.setEditable(True)
        self.cb_source.addItems(COMMON_SOURCES)
        self.cb_source.setFixedWidth(120)
        lay.addWidget(self.cb_source)

        lay.addWidget(QtWidgets.QLabel("Ch:"))
        self.cb_ch = NoScrollComboBox()
        self.cb_ch.addItems(CHANNEL_NAMES)
        self.cb_ch.setFixedWidth(50)
        lay.addWidget(self.cb_ch)

        lay.addWidget(QtWidgets.QLabel("Constant:"))
        self.sp_const = NoScrollDoubleSpinBox()
        self.sp_const.setRange(-999.0, 999.0)
        self.sp_const.setDecimals(2)
        self.sp_const.setSpecialValueText("—")
        self.sp_const.setValue(-999.0)  # sentinel for "not set"
        self.sp_const.setFixedWidth(70)
        lay.addWidget(self.sp_const)

        self.chk_invert = QtWidgets.QCheckBox("Invert")
        lay.addWidget(self.chk_invert)
        lay.addStretch()

    def to_dict(self) -> dict:
        d: dict[str, Any] = {}
        src = self.cb_source.currentText().strip()
        if src:
            d["from"] = src
            d["ch"] = self.cb_ch.currentText()
        const_val = self.sp_const.value()
        if const_val > -999.0 or not src:
            d["constant"] = round(const_val, 2) if const_val > -999.0 else 0.0
        if self.chk_invert.isChecked():
            d["invert"] = True
        return d

    def from_dict(self, d: dict) -> None:
        self.cb_source.setCurrentText(d.get("from", ""))
        self.cb_ch.setCurrentText(d.get("ch", "R"))
        const = d.get("constant")
        if const is not None:
            self.sp_const.setValue(float(const))
        else:
            self.sp_const.setValue(-999.0)
        self.chk_invert.setChecked(bool(d.get("invert", False)))


# ===========================================================================
# 输出贴图卡片
# ===========================================================================

class OutputDefCard(QtWidgets.QGroupBox):
    """一张输出贴图定义的可折叠卡片。"""
    removed = QtCore.Signal(object)  # self

    def __init__(self, index: int = 0, parent=None):
        super().__init__(f"Output #{index + 1}", parent)
        self._index = index
        self.setCheckable(True)
        self.setChecked(True)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(4)

        # 基础信息行
        row1 = QtWidgets.QHBoxLayout()
        self.w_enabled = LabeledCheck("Enabled", True, "是否启用此输出")
        row1.addWidget(self.w_enabled)
        self.w_name = LabeledLine("Output Name", "", "输出名称（如 Diffuse, Normal）")
        row1.addWidget(self.w_name)
        self.w_suffix = LabeledLine("Suffix", "", "文件后缀（如 D, N, MRO）")
        row1.addWidget(self.w_suffix)
        lay.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        self.w_category = LabeledLine("Category", "PBR", "类别标签")
        row2.addWidget(self.w_category)
        self.w_mat_param = LabeledLine("Material Param", "", "材质实例参数名")
        row2.addWidget(self.w_mat_param)
        lay.addLayout(row2)

        row3 = QtWidgets.QHBoxLayout()
        self.w_srgb = LabeledCheck("sRGB", True)
        row3.addWidget(self.w_srgb)
        self.w_format = LabeledCombo("Format", FILE_FORMATS, "PNG")
        row3.addWidget(self.w_format)
        self.w_bits = LabeledCombo("Bit Depth", [str(b) for b in BIT_DEPTHS], "8")
        row3.addWidget(self.w_bits)
        self.w_mips = LabeledCheck("Mips", True)
        row3.addWidget(self.w_mips)
        lay.addLayout(row3)

        row4 = QtWidgets.QHBoxLayout()
        self.w_allow_missing = LabeledCheck("Allow Missing", False, "源贴图缺失时仍输出")
        row4.addWidget(self.w_allow_missing)
        self.w_flip_green = LabeledCheck("Flip Green", False, "反转法线 G 通道")
        row4.addWidget(self.w_flip_green)
        self.w_alpha_pre = LabeledCheck("Alpha Premultiplied", False)
        row4.addWidget(self.w_alpha_pre)
        self.w_normal_space = LabeledCombo("Normal Space", NORMAL_SPACES, "")
        row4.addWidget(self.w_normal_space)
        lay.addLayout(row4)

        # 通道映射
        ch_group = QtWidgets.QGroupBox("Channel Mapping")
        ch_lay = QtWidgets.QVBoxLayout(ch_group)
        ch_lay.setSpacing(2)
        self.ch_rows: dict[str, ChannelDefRow] = {}
        for ch in CHANNEL_NAMES:
            row = ChannelDefRow(ch)
            self.ch_rows[ch] = row
            ch_lay.addWidget(row)
        lay.addWidget(ch_group)

        # 导入设置
        imp_group = QtWidgets.QGroupBox("Import Settings")
        imp_lay = QtWidgets.QVBoxLayout(imp_group)
        self.w_compression = LabeledCombo("Compression", COMPRESSIONS, "TC_Default", editable=True)
        imp_lay.addWidget(self.w_compression)
        self.w_lod_group = LabeledCombo("LOD Group", LOD_GROUPS, "TEXTUREGROUP_World", editable=True)
        imp_lay.addWidget(self.w_lod_group)
        imp_row = QtWidgets.QHBoxLayout()
        self.w_vt = LabeledCheck("Virtual Texture", False)
        imp_row.addWidget(self.w_vt)
        self.w_addr_x = LabeledCombo("Address X", ADDRESS_MODES, "Wrap")
        imp_row.addWidget(self.w_addr_x)
        self.w_addr_y = LabeledCombo("Address Y", ADDRESS_MODES, "Wrap")
        imp_row.addWidget(self.w_addr_y)
        self.w_mipgen = LabeledCombo("Mip Gen", MIP_GEN_MODES, "FromTextureGroup")
        imp_row.addWidget(self.w_mipgen)
        imp_lay.addLayout(imp_row)
        lay.addWidget(imp_group)

        # 删除按钮
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        btn_del = QtWidgets.QPushButton("Delete This Output")
        btn_del.setProperty("danger", True)
        btn_del.clicked.connect(lambda: self.removed.emit(self))
        btn_row.addWidget(btn_del)
        lay.addLayout(btn_row)

    # --- 序列化 ---
    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "enabled": self.w_enabled.value(),
            "output_name": self.w_name.value(),
            "suffix": self.w_suffix.value(),
            "category": self.w_category.value(),
            "srgb": self.w_srgb.value(),
            "file_format": self.w_format.value(),
            "bit_depth": int(self.w_bits.value()),
            "mips": self.w_mips.value(),
            "alpha_premultiplied": self.w_alpha_pre.value(),
            "material_parameter": self.w_mat_param.value(),
            "allow_missing": self.w_allow_missing.value(),
            "flip_green": self.w_flip_green.value(),
        }
        ns = self.w_normal_space.value()
        if ns:
            d["normal_space"] = ns
        d["channels"] = {ch: row.to_dict() for ch, row in self.ch_rows.items()}
        d["import_settings"] = {
            "compression": self.w_compression.value(),
            "lod_group": self.w_lod_group.value(),
            "virtual_texture": self.w_vt.value(),
            "address_x": self.w_addr_x.value(),
            "address_y": self.w_addr_y.value(),
            "mip_gen": self.w_mipgen.value(),
        }
        return d

    def from_dict(self, d: dict) -> None:
        self.w_enabled.set_value(d.get("enabled", True))
        self.w_name.set_value(d.get("output_name", ""))
        self.w_suffix.set_value(d.get("suffix", ""))
        self.w_category.set_value(d.get("category", "PBR"))
        self.w_mat_param.set_value(d.get("material_parameter", ""))
        self.w_srgb.set_value(d.get("srgb", True))
        self.w_format.set_value(d.get("file_format", "PNG"))
        self.w_bits.set_value(str(d.get("bit_depth", 8)))
        self.w_mips.set_value(d.get("mips", True))
        self.w_allow_missing.set_value(d.get("allow_missing", False))
        self.w_flip_green.set_value(d.get("flip_green", False))
        self.w_alpha_pre.set_value(d.get("alpha_premultiplied", False))
        self.w_normal_space.set_value(d.get("normal_space", "") or "")
        channels = d.get("channels", {})
        for ch, row in self.ch_rows.items():
            if ch in channels:
                row.from_dict(channels[ch])
        imp = d.get("import_settings", {})
        if imp:
            self.w_compression.set_value(imp.get("compression", "TC_Default"))
            self.w_lod_group.set_value(imp.get("lod_group", "TEXTUREGROUP_World"))
            self.w_vt.set_value(imp.get("virtual_texture", False))
            self.w_addr_x.set_value(imp.get("address_x", "Wrap"))
            self.w_addr_y.set_value(imp.get("address_y", "Wrap"))
            self.w_mipgen.set_value(imp.get("mip_gen", "FromTextureGroup"))

    def update_title(self, index: int) -> None:
        name = self.w_name.value() or f"Output #{index + 1}"
        self.setTitle(f"#{index + 1}  {name}")


# ===========================================================================
# 输入规则编辑（texture_input_rules.rules 表格）
# ===========================================================================

class InputRulesTable(QtWidgets.QWidget):
    """输入规则的可增删表格。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Texture Input Rules"))
        header.addStretch()
        btn_add = QtWidgets.QPushButton("+ Add Rule")
        btn_add.setProperty("secondary", True)
        btn_add.clicked.connect(self._on_add_rule)
        header.addWidget(btn_add)
        lay.addLayout(header)

        self._table = QtWidgets.QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Priority", "Patterns (comma-separated)"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 130)
        self._table.setColumnWidth(1, 60)
        self._table.verticalHeader().setVisible(False)
        lay.addWidget(self._table)

        btn_del = QtWidgets.QPushButton("Delete Selected Rule")
        btn_del.setProperty("danger", True)
        btn_del.clicked.connect(self._on_del_rule)
        lay.addWidget(btn_del)

    def _on_add_rule(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, "New Rule", "Rule name (e.g. BaseColor):")
        if ok and name.strip():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(name.strip()))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem("10"))
            self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(""))

    def _on_del_rule(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    def to_dict(self) -> dict:
        rules: dict[str, dict] = {}
        for i in range(self._table.rowCount()):
            name = (self._table.item(i, 0).text() if self._table.item(i, 0) else "").strip()
            if not name:
                continue
            pri = 10
            try:
                pri = int(self._table.item(i, 1).text())
            except Exception:
                pass
            pats_text = (self._table.item(i, 2).text() if self._table.item(i, 2) else "").strip()
            patterns = [p.strip() for p in pats_text.split(",") if p.strip()]
            rules[name] = {"priority": pri, "patterns": patterns}
        return rules

    def from_dict(self, rules: dict) -> None:
        self._table.setRowCount(0)
        for name, rd in rules.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(rd.get("priority", 10))))
            pats = rd.get("patterns", [])
            self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(", ".join(pats)))


# ===========================================================================
# 主窗口
# ===========================================================================

class ConfigEditorWindow(QtWidgets.QWidget):
    """AssetCustoms 图形化配置编辑器。"""

    def __init__(self, config_dir: str | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AssetCustoms Config Editor")
        self.resize(1060, 760)

        self._config_dir = config_dir or ""
        self._current_file: str = ""
        self._output_cards: list[OutputDefCard] = []
        self._loading = False  # prevent dirty tracking during load

        self._setup_ui()
        self.setStyleSheet(DARK_STYLE)
        self._refresh_file_combo()

    # ------------------------------------------------------------------
    # UI Layout
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ---- 顶部工具栏 ----
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(QtWidgets.QLabel("Config:"))
        self._combo_file = NoScrollComboBox()
        self._combo_file.setMinimumWidth(200)
        self._combo_file.currentIndexChanged.connect(self._on_file_combo_changed)
        toolbar.addWidget(self._combo_file, 1)

        btn_new = QtWidgets.QPushButton("New")
        btn_new.setToolTip("Create a new config file")
        btn_new.setProperty("secondary", True)
        btn_new.clicked.connect(self._on_new_config)
        toolbar.addWidget(btn_new)

        btn_dup = QtWidgets.QPushButton("Duplicate")
        btn_dup.setToolTip("Duplicate currently loaded config")
        btn_dup.setProperty("secondary", True)
        btn_dup.clicked.connect(self._on_duplicate_config)
        toolbar.addWidget(btn_dup)

        btn_del = QtWidgets.QPushButton("Delete")
        btn_del.setToolTip("Delete selected config file")
        btn_del.setProperty("danger", True)
        btn_del.clicked.connect(self._on_delete_config)
        toolbar.addWidget(btn_del)

        btn_reload = QtWidgets.QPushButton("Reload")
        btn_reload.setToolTip("Reload from disk")
        btn_reload.setProperty("secondary", True)
        btn_reload.clicked.connect(self._on_reload)
        toolbar.addWidget(btn_reload)

        btn_save = QtWidgets.QPushButton("💾 Save")
        btn_save.setToolTip("Save to disk (Ctrl+S)")
        btn_save.clicked.connect(self._on_save)
        toolbar.addWidget(btn_save)

        btn_refresh_menu = QtWidgets.QPushButton("↻ Refresh Menu")
        btn_refresh_menu.setToolTip("Refresh the import preset dropdown in Content Browser")
        btn_refresh_menu.setProperty("secondary", True)
        btn_refresh_menu.clicked.connect(self._on_refresh_import_menu)
        toolbar.addWidget(btn_refresh_menu)

        root.addLayout(toolbar)

        # ---- Tab 区域 ----
        self._tabs = QtWidgets.QTabWidget()
        root.addWidget(self._tabs, 1)

        # Tab 1: 基础设置
        self._tab_general = self._build_general_tab()
        self._tabs.addTab(self._tab_general, "General")

        # Tab 2: 输入规则
        self._tab_input = self._build_input_tab()
        self._tabs.addTab(self._tab_input, "Input Rules")

        # Tab 3: 输出定义
        self._tab_output = self._build_output_tab()
        self._tabs.addTab(self._tab_output, "Output Definitions")

        # ---- 底部状态栏 ----
        self._statusbar = QtWidgets.QLabel("Ready")
        self._statusbar.setStyleSheet(
            "background: #007ACC; color: white; padding: 3px 8px; font-size: 11px; border-radius: 2px;")
        self._statusbar.setFixedHeight(24)
        root.addWidget(self._statusbar)

        # 快捷键
        save_sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        save_sc.activated.connect(self._on_save)

    # ------ Tab: General ------
    def _build_general_tab(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setSpacing(6)

        g1 = QtWidgets.QGroupBox("Paths && Policies")
        g1l = QtWidgets.QVBoxLayout(g1)
        self.w_master_mat = LabeledLine(
            "Master Material", "", "母材质 UE 路径（空 = 不创建材质实例）")
        g1l.addWidget(self.w_master_mat)
        self.w_fallback_path = LabeledLine(
            "Fallback Import Path", "/Game/AIGC_Dropoff", "目标路径计算失败时的回退路径")
        g1l.addWidget(self.w_fallback_path)
        self.w_target_tpl = LabeledLine(
            "Target Path Template", "/Game/Assets/{Category}/{Name}",
            "资产落地目录模板，支持 {Category}, {Name}")
        g1l.addWidget(self.w_target_tpl)
        self.w_conflict = LabeledCombo(
            "Conflict Policy", CONFLICT_POLICIES, "version",
            "命名冲突策略")
        g1l.addWidget(self.w_conflict)
        lay.addWidget(g1)

        g2 = QtWidgets.QGroupBox("Asset Naming Templates")
        g2l = QtWidgets.QVBoxLayout(g2)
        self.w_nm_sm = LabeledLine("Static Mesh", "SM_{Name}", "静态网格命名模板")
        g2l.addWidget(self.w_nm_sm)
        self.w_nm_mi = LabeledLine("Material Instance", "MI_{Name}", "材质实例命名模板")
        g2l.addWidget(self.w_nm_mi)
        self.w_nm_tex = LabeledLine("Texture", "T_{Name}_{Suffix}", "贴图命名模板")
        g2l.addWidget(self.w_nm_tex)
        lay.addWidget(g2)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    # ------ Tab: Input Rules ------
    def _build_input_tab(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setSpacing(6)

        g = QtWidgets.QGroupBox("Match Settings")
        gl = QtWidgets.QVBoxLayout(g)
        self.w_match_mode = LabeledCombo("Match Mode", MATCH_MODES, "glob")
        gl.addWidget(self.w_match_mode)
        self.w_ignore_case = LabeledCheck("Ignore Case", True)
        gl.addWidget(self.w_ignore_case)
        self.w_extensions = EditableListWidget(
            "Allowed Extensions",
            [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"],
            "识别的贴图扩展名")
        gl.addWidget(self.w_extensions)
        self.w_search_roots = EditableListWidget(
            "Search Roots",
            ["{DropDir}", "{DropDir}/Textures", "{DropDir}/Maps"],
            "搜索根目录，{DropDir} = FBX 所在目录")
        gl.addWidget(self.w_search_roots)
        lay.addWidget(g)

        self._input_rules_table = InputRulesTable()
        lay.addWidget(self._input_rules_table)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    # ------ Tab: Output Definitions ------
    def _build_output_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setSpacing(4)

        btn_row = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("+ Add Output")
        btn_add.setProperty("secondary", True)
        btn_add.clicked.connect(self._on_add_output)
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._output_scroll = QtWidgets.QScrollArea()
        self._output_scroll.setWidgetResizable(True)
        self._output_container = QtWidgets.QWidget()
        self._output_layout = QtWidgets.QVBoxLayout(self._output_container)
        self._output_layout.setSpacing(8)
        self._output_layout.addStretch()
        self._output_scroll.setWidget(self._output_container)
        lay.addWidget(self._output_scroll, 1)
        return w

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------
    def _refresh_file_combo(self) -> None:
        self._combo_file.blockSignals(True)
        self._combo_file.clear()
        if self._config_dir and os.path.isdir(self._config_dir):
            for fn in sorted(os.listdir(self._config_dir)):
                if fn.lower().endswith(".jsonc"):
                    self._combo_file.addItem(fn, os.path.join(self._config_dir, fn))
        self._combo_file.blockSignals(False)
        if self._combo_file.count() > 0:
            self._on_file_combo_changed(0)

    def _on_file_combo_changed(self, index: int) -> None:
        if index < 0:
            return
        path = self._combo_file.itemData(index)
        if path:
            self._load_config(path)

    def _on_new_config(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(
            self, "New Config", "Config name (without extension):")
        if not ok or not name.strip():
            return
        name = name.strip()
        path = os.path.join(self._config_dir, f"{name}.jsonc")
        if os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Exists", f"{name}.jsonc already exists.")
            return
        default_data: dict[str, Any] = {
            "config_version": "1.1",
            "default_master_material_path": "",
            "default_fallback_import_path": "/Game/AIGC_Dropoff",
            "target_path_template": "/Game/Assets/{Category}/{Name}",
            "conflict_policy": "version",
            "asset_naming_template": {
                "static_mesh": "SM_{Name}",
                "material_instance": "MI_{Name}",
                "texture": "T_{Name}_{Suffix}",
            },
            "texture_input_rules": {
                "match_mode": "glob",
                "ignore_case": True,
                "extensions": [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"],
                "search_roots": ["{DropDir}", "{DropDir}/Textures", "{DropDir}/Maps"],
                "rules": {},
            },
            "texture_output_definitions": [],
        }
        _save_jsonc(path, default_data)
        self._refresh_file_combo()
        # 选中新建的
        idx = self._combo_file.findText(f"{name}.jsonc")
        if idx >= 0:
            self._combo_file.setCurrentIndex(idx)
        self._statusbar.setText(f"Created: {name}.jsonc")
        self._on_refresh_import_menu()

    def _on_duplicate_config(self) -> None:
        if not self._current_file:
            return
        base = os.path.splitext(os.path.basename(self._current_file))[0]
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Duplicate", "New config name:", text=f"{base}_copy")
        if not ok or not name.strip():
            return
        name = name.strip()
        dest = os.path.join(self._config_dir, f"{name}.jsonc")
        if os.path.exists(dest):
            QtWidgets.QMessageBox.warning(self, "Exists", f"{name}.jsonc already exists.")
            return
        data = self._collect_data()
        _save_jsonc(dest, data)
        self._refresh_file_combo()
        idx = self._combo_file.findText(f"{name}.jsonc")
        if idx >= 0:
            self._combo_file.setCurrentIndex(idx)
        self._statusbar.setText(f"Duplicated to: {name}.jsonc")
        self._on_refresh_import_menu()

    def _on_delete_config(self) -> None:
        if not self._current_file:
            return
        fn = os.path.basename(self._current_file)
        reply = QtWidgets.QMessageBox.warning(
            self, "Delete Config",
            f"Permanently delete {fn}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(self._current_file)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, "Error", f"Delete failed:\n{ex}")
            return
        self._current_file = ""
        self._refresh_file_combo()
        self._statusbar.setText(f"Deleted: {fn}")
        self._on_refresh_import_menu()

    def _on_reload(self) -> None:
        if self._current_file:
            self._load_config(self._current_file)

    def _on_save(self) -> None:
        if not self._current_file:
            self._statusbar.setText("No file to save")
            return
        data = self._collect_data()
        try:
            _save_jsonc(self._current_file, data)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, "Error", f"Save failed:\n{ex}")
            return
        self._statusbar.setText(f"Saved: {os.path.basename(self._current_file)}")
        self._on_refresh_import_menu()

    # ------------------------------------------------------------------
    # Load / Collect
    # ------------------------------------------------------------------
    def _load_config(self, path: str) -> None:
        try:
            data = _load_jsonc(path)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load:\n{ex}")
            return

        self._loading = True
        self._current_file = path

        # General
        self.w_master_mat.set_value(data.get("default_master_material_path", ""))
        self.w_fallback_path.set_value(data.get("default_fallback_import_path", "/Game/AIGC_Dropoff"))
        self.w_target_tpl.set_value(data.get("target_path_template", "/Game/Assets/{Category}/{Name}"))
        self.w_conflict.set_value(data.get("conflict_policy", "version"))

        ant = data.get("asset_naming_template", {})
        self.w_nm_sm.set_value(ant.get("static_mesh", "SM_{Name}"))
        self.w_nm_mi.set_value(ant.get("material_instance", "MI_{Name}"))
        self.w_nm_tex.set_value(ant.get("texture", "T_{Name}_{Suffix}"))

        # Input rules
        tir = data.get("texture_input_rules", {})
        self.w_match_mode.set_value(tir.get("match_mode", "glob"))
        self.w_ignore_case.set_value(tir.get("ignore_case", True))
        self.w_extensions.set_values(tir.get("extensions",
                                             [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"]))
        self.w_search_roots.set_values(tir.get("search_roots",
                                                ["{DropDir}", "{DropDir}/Textures", "{DropDir}/Maps"]))
        self._input_rules_table.from_dict(tir.get("rules", {}))

        # Output definitions
        self._clear_output_cards()
        for od in data.get("texture_output_definitions", []):
            card = self._add_output_card()
            card.from_dict(od)
        self._renumber_output_cards()

        self._loading = False
        self._statusbar.setText(f"Loaded: {os.path.basename(path)}")

    def _collect_data(self) -> dict:
        """从表单控件收集完整配置 dict。"""
        data: dict[str, Any] = {
            "config_version": "1.1",
            "default_master_material_path": self.w_master_mat.value(),
            "default_fallback_import_path": self.w_fallback_path.value(),
            "target_path_template": self.w_target_tpl.value(),
            "conflict_policy": self.w_conflict.value(),
            "asset_naming_template": {
                "static_mesh": self.w_nm_sm.value(),
                "material_instance": self.w_nm_mi.value(),
                "texture": self.w_nm_tex.value(),
            },
            "texture_input_rules": {
                "match_mode": self.w_match_mode.value(),
                "ignore_case": self.w_ignore_case.value(),
                "extensions": self.w_extensions.values(),
                "search_roots": self.w_search_roots.values(),
                "rules": self._input_rules_table.to_dict(),
            },
            "texture_output_definitions": [c.to_dict() for c in self._output_cards],
        }
        return data

    # ------------------------------------------------------------------
    # Output cards management
    # ------------------------------------------------------------------
    def _add_output_card(self) -> OutputDefCard:
        card = OutputDefCard(len(self._output_cards))
        card.removed.connect(self._on_remove_output)
        self._output_cards.append(card)
        # 插入 stretch 之前
        self._output_layout.insertWidget(self._output_layout.count() - 1, card)
        return card

    def _on_add_output(self) -> None:
        card = self._add_output_card()
        self._renumber_output_cards()
        self._output_scroll.ensureWidgetVisible(card)

    def _on_remove_output(self, card: OutputDefCard) -> None:
        if card in self._output_cards:
            self._output_cards.remove(card)
            card.setParent(None)
            card.deleteLater()
            self._renumber_output_cards()

    def _clear_output_cards(self) -> None:
        for card in self._output_cards:
            card.setParent(None)
            card.deleteLater()
        self._output_cards.clear()

    def _renumber_output_cards(self) -> None:
        for i, card in enumerate(self._output_cards):
            card.update_title(i)

    # ------------------------------------------------------------------
    # Refresh import menu (ToolMenus)
    # ------------------------------------------------------------------
    @staticmethod
    def _on_refresh_import_menu() -> None:
        """Re-register the import dropdown so new/modified/deleted configs take effect."""
        try:
            import unreal
            ui = getattr(unreal, "ASSET_CUSTOMS_UI", None)
            if ui is not None and hasattr(ui, "register_all"):
                ui.register_all()
                unreal.log("[AssetCustoms] Import menu refreshed.")
            else:
                unreal.log_warning("[AssetCustoms] UI singleton not found; cannot refresh menu.")
        except Exception:
            pass  # Outside UE — silently ignore

    # ------------------------------------------------------------------
    # Close guard
    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.accept()


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------

def open_config_editor(config_dir: str | None = None) -> ConfigEditorWindow:
    """创建并显示配置编辑器窗口。返回窗口实例。"""
    window = ConfigEditorWindow(config_dir=config_dir)
    window.show()
    return window
