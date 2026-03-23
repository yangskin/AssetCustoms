"""AssetCustoms 图形化配置编辑器：PySide6 表单 GUI。

面向美术人员，无需手写 JSON — 通过下拉框、输入框、复选框等控件
可视化编辑 Content/Config/AssetCustoms/*.jsonc 配置文件。
支持：新建 / 选择 / 删除 / 读取 / 保存。

Config v2.0 三段式管线模型：Input → Processing → Output
"""
from __future__ import annotations

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
    """Serialize config dict to a well-commented JSONC string (v2.0)."""
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    lines = raw.split("\n")
    result: list[str] = []
    in_defs = False
    def_index = 0
    td = (data.get("processing") or {}).get("texture_definitions", [])

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Section comments
        if stripped.startswith('"config_version"'):
            result.append("  // === AssetCustoms 配置 v2.0 (JSONC) ===")
            result.append("  // 运行时占位符：{Name} {Suffix} {Category} {DropDir}")
        elif stripped.startswith('"input"') and indent == 2:
            result.append("")
            result.append("  // === 阶段一：传入（Input）— 拿到什么、怎么识别 ===")
        elif stripped.startswith('"processing"') and indent == 2:
            result.append("")
            result.append("  // === 阶段二：处理（Processing）— 怎么加工 ===")
        elif stripped.startswith('"texture_definitions"') and indent == 4:
            if not stripped.rstrip().endswith("[]") and not stripped.rstrip().endswith("[],"):
                in_defs = True
                def_index = 0
        elif stripped.startswith('"output"') and indent == 2:
            result.append("")
            result.append("  // === 阶段三：交付（Output）— 放哪里、叫什么、UE 怎么设 ===")

        # Per-definition comment
        if in_defs and stripped == "{":
            if def_index < len(td):
                name = td[def_index].get("name", f"Definition {def_index + 1}")
                spaces = " " * indent
                result.append(f"{spaces}// --- {name} ---")
                def_index += 1

        if in_defs and stripped.rstrip(",") == "]" and indent <= 4:
            in_defs = False

        result.append(line)

    return "\n".join(result) + "\n"


def _save_jsonc(path: str, data: dict) -> None:
    """Save config dict as a .jsonc file with section comments."""
    text = _dict_to_jsonc(data)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# 多语言支持
# ---------------------------------------------------------------------------

_LANG: str = "en"

_TR: dict[str, dict[str, str]] = {
    # Window
    "window_title":          {"en": "AssetCustoms Config Editor", "zh": "AssetCustoms 配置编辑器"},
    # Toolbar
    "config_label":          {"en": "Config:", "zh": "配置:"},
    "btn_new":               {"en": "New", "zh": "新建"},
    "btn_new_tip":           {"en": "Create a new config file", "zh": "创建新配置文件"},
    "btn_dup":               {"en": "Duplicate", "zh": "复制"},
    "btn_dup_tip":           {"en": "Duplicate currently loaded config", "zh": "复制当前配置"},
    "btn_del":               {"en": "Delete", "zh": "删除"},
    "btn_del_tip":           {"en": "Delete selected config file", "zh": "删除选中的配置文件"},
    "btn_reload":            {"en": "Reload", "zh": "重载"},
    "btn_reload_tip":        {"en": "Reload from disk", "zh": "从磁盘重新加载"},
    "btn_save":              {"en": "💾 Save", "zh": "💾 保存"},
    "btn_save_tip":          {"en": "Save to disk (Ctrl+S)", "zh": "保存到磁盘 (Ctrl+S)"},
    "btn_refresh":           {"en": "↻ Refresh Menu", "zh": "↻ 刷新菜单"},
    "btn_refresh_tip":       {"en": "Refresh the import preset dropdown in Content Browser",
                              "zh": "刷新内容浏览器中的导入预设下拉菜单"},
    # Tabs (v2.0 三段式)
    "tab_input":             {"en": "Input", "zh": "输入"},
    "tab_processing":        {"en": "Processing", "zh": "处理"},
    "tab_output":            {"en": "Output", "zh": "输出"},
    # Input tab
    "grp_match":             {"en": "Match Settings", "zh": "匹配设置"},
    "match_mode":            {"en": "Match Mode", "zh": "匹配模式"},
    "ignore_case":           {"en": "Ignore Case", "zh": "忽略大小写"},
    "extensions":            {"en": "Allowed Extensions", "zh": "允许的扩展名"},
    "extensions_tip":        {"en": "Recognized texture file extensions", "zh": "识别的贴图扩展名"},
    "search_roots":          {"en": "Search Roots", "zh": "搜索根目录"},
    "search_roots_tip":      {"en": "Search root dirs, {DropDir} = FBX directory",
                              "zh": "搜索根目录，{DropDir} = FBX 所在目录"},
    "input_rules_hdr":       {"en": "Texture Input Rules", "zh": "贴图输入规则"},
    "btn_add_rule":          {"en": "+ Add Rule", "zh": "+ 添加规则"},
    "btn_del_rule":          {"en": "Delete Selected Rule", "zh": "删除选中规则"},
    "col_name":              {"en": "Name", "zh": "名称"},
    "col_priority":          {"en": "Priority", "zh": "优先级"},
    "col_patterns":          {"en": "Patterns (comma-separated)", "zh": "匹配模式（逗号分隔）"},
    # Processing tab
    "grp_conflict":          {"en": "Processing Policy", "zh": "处理策略"},
    "conflict":              {"en": "Conflict Policy", "zh": "冲突策略"},
    "conflict_tip":          {"en": "Naming conflict policy", "zh": "命名冲突策略"},
    "btn_add_def":           {"en": "+ Add Definition", "zh": "+ 添加定义"},
    "btn_del_def":           {"en": "Delete This Definition", "zh": "删除此定义"},
    "def_enabled":           {"en": "Enabled", "zh": "启用"},
    "def_enabled_tip":       {"en": "Enable this texture definition", "zh": "是否启用此贴图定义"},
    "def_name":              {"en": "Name", "zh": "名称"},
    "def_name_tip":          {"en": "Definition name (e.g. Diffuse, Normal)", "zh": "定义名称（如 Diffuse, Normal）"},
    "def_suffix":            {"en": "Suffix", "zh": "后缀"},
    "def_suffix_tip":        {"en": "File suffix (e.g. D, N, MRO)", "zh": "文件后缀（如 D, N, MRO）"},
    "def_category":          {"en": "Category", "zh": "类别"},
    "def_category_tip":      {"en": "Category tag", "zh": "类别标签"},
    "def_srgb":              {"en": "sRGB", "zh": "sRGB"},
    "def_format":            {"en": "Format", "zh": "格式"},
    "def_bits":              {"en": "Bit Depth", "zh": "位深度"},
    "def_mips":              {"en": "Mips", "zh": "Mips"},
    "def_allow_miss":        {"en": "Allow Missing", "zh": "允许缺失"},
    "def_allow_miss_tip":    {"en": "Still output when source is missing", "zh": "源贴图缺失时仍输出"},
    "def_flip_g":            {"en": "Flip Green", "zh": "翻转绿色通道"},
    "def_flip_g_tip":        {"en": "Invert normal G channel", "zh": "反转法线 G 通道"},
    "def_alpha_pre":         {"en": "Alpha Premultiplied", "zh": "预乘 Alpha"},
    "def_normal_sp":         {"en": "Normal Space", "zh": "法线空间"},
    "grp_channels":          {"en": "Channel Mapping", "zh": "通道映射"},
    # Output tab
    "grp_paths":             {"en": "Paths", "zh": "路径"},
    "target_tpl":            {"en": "Target Path Template", "zh": "目标路径模板"},
    "target_tpl_tip":        {"en": "Asset directory template, supports {Category}, {Name}. Empty = use Content Browser selected directory.",
                              "zh": "资产落地目录模板，支持 {Category}, {Name}。留空 = 使用内容浏览器当前选中目录。"},
    "target_tpl_ph":         {"en": "Empty = Content Browser dir. e.g. /Game/Assets/{Category}/{Name}",
                              "zh": "留空 = 内容浏览器目录。示例: /Game/Assets/{Category}/{Name}"},
    "fallback_path":         {"en": "Fallback Import Path", "zh": "回退导入路径"},
    "fallback_path_tip":     {"en": "Fallback path when target calculation fails", "zh": "目标路径计算失败时的回退路径"},
    "grp_naming":            {"en": "Asset Naming Templates", "zh": "资产命名模板"},
    "nm_sm":                 {"en": "Static Mesh", "zh": "静态网格"},
    "nm_sm_tip":             {"en": "Static mesh naming template", "zh": "静态网格命名模板"},
    "nm_mi":                 {"en": "Material Instance", "zh": "材质实例"},
    "nm_mi_tip":             {"en": "Material instance naming template", "zh": "材质实例命名模板"},
    "nm_tex":                {"en": "Texture", "zh": "贴图"},
    "nm_tex_tip":            {"en": "Texture naming template", "zh": "贴图命名模板"},
    "grp_subdirs":           {"en": "Asset Subdirectories", "zh": "资产子目录"},
    "subdir_mode":           {"en": "Layout Mode", "zh": "布局模式"},
    "subdir_mode_tip":       {"en": "Aggregated: all in one folder; Separate: split into subdirectories",
                              "zh": "聚合：全部放同一目录；独立文件夹：按类型分子目录"},
    "subdir_aggregated":     {"en": "Aggregated (all in root)", "zh": "聚合（全放根目录）"},
    "subdir_separate":       {"en": "Separate Folders", "zh": "独立文件夹"},
    "subdir_sm":             {"en": "Static Mesh Subdir", "zh": "静态网格子目录"},
    "subdir_sm_tip":         {"en": "Subdirectory for static mesh (empty = root)",
                              "zh": "静态网格子目录（空 = 放在根目录）"},
    "subdir_mi":             {"en": "Material Instance Subdir", "zh": "材质实例子目录"},
    "subdir_mi_tip":         {"en": "Subdirectory for material instances (empty = root)",
                              "zh": "材质实例子目录（空 = 放在根目录）"},
    "subdir_tex":            {"en": "Texture Subdir", "zh": "贴图子目录"},
    "subdir_tex_tip":        {"en": "Subdirectory for textures (empty = root)",
                              "zh": "贴图子目录（空 = 放在根目录）"},
    "grp_material":          {"en": "Material", "zh": "材质"},
    "master_mat":            {"en": "Master Material", "zh": "母材质"},
    "master_mat_tip":        {"en": "Master material UE path (empty = no MI)", "zh": "母材质 UE 路径（空 = 不创建材质实例）"},
    "param_bindings":        {"en": "Parameter Bindings (suffix → MI param)", "zh": "参数绑定（后缀 → MI 参数名）"},
    "btn_add_binding":       {"en": "+ Add Binding", "zh": "+ 添加绑定"},
    "btn_del_binding":       {"en": "Delete Selected", "zh": "删除选中"},
    "col_suffix":            {"en": "Suffix", "zh": "后缀"},
    "col_param":             {"en": "Parameter Name", "zh": "参数名"},
    "grp_import_defaults":   {"en": "Texture Import Defaults", "zh": "贴图导入默认值"},
    "imp_compress":          {"en": "Compression", "zh": "压缩"},
    "imp_lod":               {"en": "LOD Group", "zh": "LOD 组"},
    "imp_vt":                {"en": "Virtual Texture", "zh": "虚拟纹理"},
    "imp_addr_x":            {"en": "Address X", "zh": "寻址 X"},
    "imp_addr_y":            {"en": "Address Y", "zh": "寻址 Y"},
    "imp_mipgen":            {"en": "Mip Gen", "zh": "Mip 生成"},
    "grp_import_overrides":  {"en": "Texture Import Overrides (per-suffix)", "zh": "贴图导入覆盖（按后缀）"},
    "btn_add_override":      {"en": "+ Add Override", "zh": "+ 添加覆盖"},
    "btn_del_override":      {"en": "Delete This Override", "zh": "删除此覆盖"},
    "override_suffix":       {"en": "Suffix", "zh": "后缀"},
    # Channel row
    "ch_source":             {"en": "Source:", "zh": "来源:"},
    "ch_ch":                 {"en": "Ch:", "zh": "通道:"},
    "ch_const":              {"en": "Constant:", "zh": "常量:"},
    "ch_invert":             {"en": "Invert", "zh": "反转"},
    # Status
    "st_ready":              {"en": "Ready", "zh": "就绪"},
    "st_no_file":            {"en": "No file to save", "zh": "没有可保存的文件"},
    "st_created":            {"en": "Created: {n}", "zh": "已创建: {n}"},
    "st_saved":              {"en": "Saved: {n}", "zh": "已保存: {n}"},
    "st_deleted":            {"en": "Deleted: {n}", "zh": "已删除: {n}"},
    "st_duplicated":         {"en": "Duplicated to: {n}", "zh": "已复制为: {n}"},
    "st_loaded":             {"en": "Loaded: {n}", "zh": "已加载: {n}"},
    # Dialogs
    "dlg_new":               {"en": "New Config", "zh": "新建配置"},
    "dlg_new_p":             {"en": "Config name (without extension):", "zh": "配置名称（不含扩展名）:"},
    "dlg_dup":               {"en": "Duplicate", "zh": "复制配置"},
    "dlg_dup_p":             {"en": "New config name:", "zh": "新配置名称:"},
    "dlg_del":               {"en": "Delete Config", "zh": "删除配置"},
    "dlg_del_p":             {"en": "Permanently delete {n}?", "zh": "永久删除 {n}？"},
    "dlg_exists":            {"en": "Exists", "zh": "已存在"},
    "dlg_exists_p":          {"en": "{n} already exists.", "zh": "{n} 已存在。"},
    "dlg_error":             {"en": "Error", "zh": "错误"},
    "dlg_del_fail":          {"en": "Delete failed:\n{e}", "zh": "删除失败:\n{e}"},
    "dlg_save_fail":         {"en": "Save failed:\n{e}", "zh": "保存失败:\n{e}"},
    "dlg_load_fail":         {"en": "Failed to load:\n{e}", "zh": "加载失败:\n{e}"},
    "dlg_add_item":          {"en": "Add Item", "zh": "添加项目"},
    "dlg_add_item_p":        {"en": "Value:", "zh": "值:"},
    "dlg_add_rule":          {"en": "New Rule", "zh": "新建规则"},
    "dlg_add_rule_p":        {"en": "Rule name (e.g. BaseColor):", "zh": "规则名称（如 BaseColor）:"},
    # Mesh Import (ADR-0003)
    "grp_mesh_import":       {"en": "Mesh Import Settings", "zh": "模型导入设置"},
    "mi_scale":              {"en": "Uniform Scale", "zh": "统一缩放"},
    "mi_scale_tip":          {"en": "Uniform scale factor applied on import", "zh": "导入时的统一缩放系数"},
    "mi_skeletal":           {"en": "Import as Skeletal", "zh": "作为骨骼网格导入"},
    "mi_skeletal_tip":       {"en": "Import as skeletal mesh instead of static mesh", "zh": "作为骨骼网格而非静态网格导入"},
    "mi_normal_import":      {"en": "Normal Import Method", "zh": "法线导入方式"},
    "mi_normal_import_tip":  {"en": "How normals are imported from FBX", "zh": "FBX 法线导入方式"},
    "mi_normal_gen":         {"en": "Normal Generation", "zh": "法线生成方式"},
    "mi_normal_gen_tip":     {"en": "Normal generation method when computing normals", "zh": "计算法线时的生成方式"},
    "mi_weighted_normals":   {"en": "Compute Weighted Normals", "zh": "计算加权法线"},
    "mi_weighted_normals_tip": {"en": "Use face area/angle for weighted normals", "zh": "使用面面积/角度计算加权法线"},
    "mi_vertex_color":       {"en": "Vertex Color Import", "zh": "顶点色导入"},
    "mi_vertex_color_tip":   {"en": "How vertex colors are handled on import", "zh": "导入时如何处理顶点色"},
    "mi_animations":         {"en": "Import Animations", "zh": "导入动画"},
    "mi_animations_tip":     {"en": "Import animation data from FBX", "zh": "从 FBX 导入动画数据"},
    "mi_collision":          {"en": "Auto Generate Collision", "zh": "自动生成碰撞"},
    "mi_collision_tip":      {"en": "Automatically generate simple collision on import", "zh": "导入时自动生成简单碰撞"},
    "mi_combine":            {"en": "Combine Meshes", "zh": "合并网格"},
    "mi_combine_tip":        {"en": "Combine all meshes into a single mesh", "zh": "将所有网格合并为单个网格"},
    "mi_degenerates":        {"en": "Remove Degenerates", "zh": "移除退化三角形"},
    "mi_degenerates_tip":    {"en": "Remove degenerate triangles during import", "zh": "导入时移除退化三角形"},
    "mi_nanite":             {"en": "Build Nanite", "zh": "构建 Nanite"},
    "mi_nanite_tip":         {"en": "Enable Nanite for this mesh", "zh": "为此网格启用 Nanite"},
    "mi_rev_idx":            {"en": "Build Reversed Index Buffer", "zh": "构建反向索引缓冲"},
    "mi_rev_idx_tip":        {"en": "Build reversed index buffer for back-face rendering", "zh": "构建反向索引缓冲用于背面渲染"},
    "mi_lightmap":           {"en": "Generate Lightmap UVs", "zh": "生成光照贴图 UV"},
    "mi_lightmap_tip":       {"en": "Auto-generate lightmap UVs on import", "zh": "导入时自动生成光照贴图 UV"},
    "mi_convert_scene":      {"en": "Convert Scene", "zh": "转换场景"},
    "mi_convert_unit":       {"en": "Convert Scene Unit", "zh": "转换场景单位"},
    "mi_force_front_x":      {"en": "Force Front X Axis", "zh": "强制前方为 X 轴"},
    "mi_lods":               {"en": "Import Mesh LODs", "zh": "导入网格 LOD"},
    "mi_lods_tip":           {"en": "Import LOD meshes from FBX", "zh": "从 FBX 导入 LOD 网格"},
    "mi_lod_group":          {"en": "Static Mesh LOD Group", "zh": "静态网格 LOD 组"},
    "mi_import_mat":         {"en": "Import Materials", "zh": "导入材质"},
    "mi_import_mat_tip":     {"en": "Import materials from FBX", "zh": "从 FBX 导入材质"},
    "mi_import_tex":         {"en": "Import Textures", "zh": "导入贴图"},
    "mi_import_tex_tip":     {"en": "Import textures from FBX", "zh": "从 FBX 导入贴图"},
    "mi_reorder_mat":        {"en": "Reorder Material to FBX Order", "zh": "按 FBX 顺序排列材质"},
    "mi_reorder_mat_tip":    {"en": "Reorder material slots to match FBX order", "zh": "按 FBX 中的顺序排列材质槽"},
    # SkeletalMesh 专有
    "mi_skeleton_path":      {"en": "Skeleton Asset", "zh": "骨骼资产"},
    "mi_skeleton_path_tip":  {"en": "Existing Skeleton asset path (e.g. /Game/Characters/SK_Mannequin_Skeleton)", "zh": "已有骨骼资产路径（如 /Game/Characters/SK_Mannequin_Skeleton）"},
    "mi_create_phys":        {"en": "Create Physics Asset", "zh": "创建物理资产"},
    "mi_create_phys_tip":    {"en": "Create a PhysicsAsset alongside the SkeletalMesh", "zh": "与骨骼网格一并创建物理资产"},
    "mi_morph_targets":      {"en": "Import Morph Targets", "zh": "导入变形目标"},
    "mi_morph_targets_tip":  {"en": "Import blend shapes / morph targets from FBX", "zh": "从 FBX 导入混合变形/变形目标"},
    "mi_bone_hierarchy":     {"en": "Import Meshes in Bone Hierarchy", "zh": "导入骨骼层级中的网格"},
    "mi_bone_hierarchy_tip": {"en": "Import meshes nested in the bone hierarchy", "zh": "导入嵌套在骨骼层级中的网格"},
    "mi_update_ref_pose":    {"en": "Update Skeleton Reference Pose", "zh": "更新骨骼参考姿势"},
    "mi_update_ref_pose_tip": {"en": "Update existing Skeleton reference pose on re-import", "zh": "重新导入时更新已有骨骼的参考姿势"},
    "mi_t0_ref_pose":        {"en": "Use T0 as Reference Pose", "zh": "使用 T0 作为参考姿势"},
    "mi_t0_ref_pose_tip":    {"en": "Use frame 0 as the reference pose instead of bind pose", "zh": "使用第 0 帧而非绑定姿势作为参考姿势"},
    "mi_preserve_smooth":    {"en": "Preserve Smoothing Groups", "zh": "保留平滑组"},
    "mi_preserve_smooth_tip": {"en": "Preserve FBX smoothing groups on import", "zh": "导入时保留 FBX 平滑组"},
    "mi_content_type":       {"en": "Import Content Type", "zh": "导入内容类型"},
    "mi_content_type_tip":   {"en": "What to import: All, Geometry only, or Skinning Weights only", "zh": "导入内容：全部、仅几何体或仅蒙皮权重"},
}


def _t(key: str, **kw) -> str:
    """Return translated string for current language."""
    entry = _TR.get(key, {})
    text = entry.get(_LANG, entry.get("en", key))
    return text.format(**kw) if kw else text


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
# ── Mesh Import 枚举常量（ADR-0003）──
NORMAL_IMPORT_METHODS = ["ComputeNormals", "ImportNormals", "ImportNormalsAndTangents"]
NORMAL_GEN_METHODS = ["BuiltIn", "MikkTSpace"]
VERTEX_COLOR_OPTIONS = ["Replace", "Ignore", "Override"]
MESH_LOD_GROUPS = ["None", "LargeWorld", "SmallProp", "MediumProp"]
IMPORT_CONTENT_TYPES = ["All", "Geometry", "SkinningWeights"]
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
        self._lbl = QtWidgets.QLabel(label)
        self._lbl.setFixedWidth(160)
        self._lbl.setToolTip(tooltip)
        self.edit = QtWidgets.QLineEdit(value)
        self.edit.setToolTip(tooltip)
        lay.addWidget(self._lbl)
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
        self._lbl = QtWidgets.QLabel(label)
        self._lbl.setFixedWidth(160)
        self._lbl.setToolTip(tooltip)
        self.combo = NoScrollComboBox()
        self.combo.setEditable(editable)
        self.combo.addItems(items)
        self.combo.setToolTip(tooltip)
        if current in items:
            self.combo.setCurrentText(current)
        elif editable and current:
            self.combo.setCurrentText(current)
        lay.addWidget(self._lbl)
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
        self._lbl = QtWidgets.QLabel(label)
        self._lbl.setFixedWidth(160)
        self._lbl.setToolTip(tooltip)
        self.spin = NoScrollSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value)
        self.spin.setToolTip(tooltip)
        lay.addWidget(self._lbl)
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
        self._lbl = QtWidgets.QLabel(label)
        self._lbl.setFixedWidth(160)
        self._lbl.setToolTip(tooltip)
        self.spin = NoScrollDoubleSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setDecimals(decimals)
        self.spin.setValue(value)
        self.spin.setToolTip(tooltip)
        lay.addWidget(self._lbl)
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
        self._title_lbl = QtWidgets.QLabel(label)
        self._title_lbl.setToolTip(tooltip)
        main.addWidget(self._title_lbl)

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
        text, ok = QtWidgets.QInputDialog.getText(self, _t("dlg_add_item"), _t("dlg_add_item_p"))
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

        self._lbl_source = QtWidgets.QLabel("Source:")
        lay.addWidget(self._lbl_source)
        self.cb_source = NoScrollComboBox()
        self.cb_source.setEditable(True)
        self.cb_source.addItems(COMMON_SOURCES)
        self.cb_source.setFixedWidth(120)
        lay.addWidget(self.cb_source)

        self._lbl_ch = QtWidgets.QLabel("Ch:")
        lay.addWidget(self._lbl_ch)
        self.cb_ch = NoScrollComboBox()
        self.cb_ch.addItems(CHANNEL_NAMES)
        self.cb_ch.setFixedWidth(50)
        lay.addWidget(self.cb_ch)

        self._lbl_const = QtWidgets.QLabel("Constant:")
        lay.addWidget(self._lbl_const)
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

    def retranslate(self) -> None:
        self._lbl_source.setText(_t("ch_source"))
        self._lbl_ch.setText(_t("ch_ch"))
        self._lbl_const.setText(_t("ch_const"))
        self.chk_invert.setText(_t("ch_invert"))

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
# 参数绑定表（suffix → MI parameter name）
# ===========================================================================

class ParameterBindingsTable(QtWidgets.QWidget):
    """suffix → 材质实例参数名 的映射表。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QHBoxLayout()
        self._hdr_lbl = QtWidgets.QLabel(_t("param_bindings"))
        header.addWidget(self._hdr_lbl)
        header.addStretch()
        self._btn_add = QtWidgets.QPushButton(_t("btn_add_binding"))
        self._btn_add.setProperty("secondary", True)
        self._btn_add.clicked.connect(self._on_add)
        header.addWidget(self._btn_add)
        lay.addLayout(header)

        self._table = QtWidgets.QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels([_t("col_suffix"), _t("col_param")])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 100)
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        lay.addWidget(self._table)

        self._btn_del = QtWidgets.QPushButton(_t("btn_del_binding"))
        self._btn_del.setProperty("danger", True)
        self._btn_del.clicked.connect(self._on_del)
        lay.addWidget(self._btn_del)

    def _on_add(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(""))
        self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(""))
        self._update_height()

    def _on_del(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._update_height()

    def _update_height(self) -> None:
        """根据行数自适应表格高度，确保所有行完全展开可见。"""
        row_count = max(self._table.rowCount(), 1)
        row_h = self._table.verticalHeader().defaultSectionSize()
        header_h = self._table.horizontalHeader().height()
        # 额外 4px 边距避免出现滚动条
        self._table.setFixedHeight(header_h + row_h * row_count + 4)

    def to_dict(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for i in range(self._table.rowCount()):
            suffix = (self._table.item(i, 0).text() if self._table.item(i, 0) else "").strip()
            param = (self._table.item(i, 1).text() if self._table.item(i, 1) else "").strip()
            if suffix and param:
                result[suffix] = param
        return result

    def from_dict(self, d: dict[str, str]) -> None:
        self._table.setRowCount(0)
        for suffix, param in d.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(suffix))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(param))
        self._update_height()

    def retranslate(self) -> None:
        self._hdr_lbl.setText(_t("param_bindings"))
        self._btn_add.setText(_t("btn_add_binding"))
        self._btn_del.setText(_t("btn_del_binding"))
        self._table.setHorizontalHeaderLabels([_t("col_suffix"), _t("col_param")])


# ===========================================================================
# 导入覆盖卡片（单个 suffix 的 import override）
# ===========================================================================

class ImportOverrideCard(QtWidgets.QGroupBox):
    """单个后缀的导入设置覆盖卡片。空字段表示沿用默认值。"""
    removed = QtCore.Signal(object)

    def __init__(self, suffix: str = "", parent=None):
        super().__init__(f"Override: {suffix or '?'}", parent)
        self._build_ui(suffix)

    def _build_ui(self, suffix: str) -> None:
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(4)

        self.w_suffix = LabeledLine(_t("override_suffix"), suffix)
        lay.addWidget(self.w_suffix)

        self.w_compression = LabeledCombo(
            _t("imp_compress"), [""] + COMPRESSIONS, "", editable=True)
        lay.addWidget(self.w_compression)
        self.w_lod_group = LabeledCombo(
            _t("imp_lod"), [""] + LOD_GROUPS, "", editable=True)
        lay.addWidget(self.w_lod_group)

        imp_row = QtWidgets.QHBoxLayout()
        self.w_vt = LabeledCombo(_t("imp_vt"), ["", "true", "false"], "")
        imp_row.addWidget(self.w_vt)
        self.w_addr_x = LabeledCombo(_t("imp_addr_x"), [""] + ADDRESS_MODES, "")
        imp_row.addWidget(self.w_addr_x)
        self.w_addr_y = LabeledCombo(_t("imp_addr_y"), [""] + ADDRESS_MODES, "")
        imp_row.addWidget(self.w_addr_y)
        self.w_mipgen = LabeledCombo(_t("imp_mipgen"), [""] + MIP_GEN_MODES, "")
        imp_row.addWidget(self.w_mipgen)
        lay.addLayout(imp_row)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self._btn_del = QtWidgets.QPushButton(_t("btn_del_override"))
        self._btn_del.setProperty("danger", True)
        self._btn_del.clicked.connect(lambda: self.removed.emit(self))
        btn_row.addWidget(self._btn_del)
        lay.addLayout(btn_row)

    def to_tuple(self) -> tuple[str, dict]:
        """Return (suffix, override_dict). Empty values are omitted."""
        suffix = self.w_suffix.value().strip()
        d: dict[str, Any] = {}
        if self.w_compression.value():
            d["compression"] = self.w_compression.value()
        if self.w_lod_group.value():
            d["lod_group"] = self.w_lod_group.value()
        vt = self.w_vt.value()
        if vt:
            d["virtual_texture"] = vt == "true"
        if self.w_addr_x.value():
            d["address_x"] = self.w_addr_x.value()
        if self.w_addr_y.value():
            d["address_y"] = self.w_addr_y.value()
        if self.w_mipgen.value():
            d["mip_gen"] = self.w_mipgen.value()
        return suffix, d

    def from_data(self, suffix: str, d: dict) -> None:
        self.w_suffix.set_value(suffix)
        self.setTitle(f"Override: {suffix}")
        self.w_compression.set_value(d.get("compression", ""))
        self.w_lod_group.set_value(d.get("lod_group", ""))
        vt = d.get("virtual_texture")
        self.w_vt.set_value("true" if vt is True else "false" if vt is False else "")
        self.w_addr_x.set_value(d.get("address_x", ""))
        self.w_addr_y.set_value(d.get("address_y", ""))
        self.w_mipgen.set_value(d.get("mip_gen", ""))

    def retranslate(self) -> None:
        self.w_suffix._lbl.setText(_t("override_suffix"))
        self.w_compression._lbl.setText(_t("imp_compress"))
        self.w_lod_group._lbl.setText(_t("imp_lod"))
        self.w_vt._lbl.setText(_t("imp_vt"))
        self.w_addr_x._lbl.setText(_t("imp_addr_x"))
        self.w_addr_y._lbl.setText(_t("imp_addr_y"))
        self.w_mipgen._lbl.setText(_t("imp_mipgen"))
        self._btn_del.setText(_t("btn_del_override"))


# ===========================================================================
# 贴图定义卡片（processing.texture_definitions 的一项）
# ===========================================================================

class OutputDefCard(QtWidgets.QGroupBox):
    """一张贴图处理定义的可折叠卡片。"""
    removed = QtCore.Signal(object)  # self

    def __init__(self, index: int = 0, parent=None):
        super().__init__(f"#{index + 1}", parent)
        self._index = index
        self.setCheckable(True)
        self.setChecked(True)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(4)

        # 基础信息行
        row1 = QtWidgets.QHBoxLayout()
        self.w_enabled = LabeledCheck("Enabled", True, _t("def_enabled_tip"))
        row1.addWidget(self.w_enabled)
        self.w_name = LabeledLine("Name", "", _t("def_name_tip"))
        row1.addWidget(self.w_name)
        self.w_suffix = LabeledLine("Suffix", "", _t("def_suffix_tip"))
        row1.addWidget(self.w_suffix)
        lay.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        self.w_category = LabeledLine("Category", "PBR", _t("def_category_tip"))
        row2.addWidget(self.w_category)
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
        self.w_allow_missing = LabeledCheck("Allow Missing", False, _t("def_allow_miss_tip"))
        row4.addWidget(self.w_allow_missing)
        self.w_flip_green = LabeledCheck("Flip Green", False, _t("def_flip_g_tip"))
        row4.addWidget(self.w_flip_green)
        self.w_alpha_pre = LabeledCheck("Alpha Premultiplied", False)
        row4.addWidget(self.w_alpha_pre)
        self.w_normal_space = LabeledCombo("Normal Space", NORMAL_SPACES, "")
        row4.addWidget(self.w_normal_space)
        lay.addLayout(row4)

        # 通道映射
        self._grp_channels = QtWidgets.QGroupBox("Channel Mapping")
        ch_lay = QtWidgets.QVBoxLayout(self._grp_channels)
        ch_lay.setSpacing(2)
        self.ch_rows: dict[str, ChannelDefRow] = {}
        for ch in CHANNEL_NAMES:
            row = ChannelDefRow(ch)
            self.ch_rows[ch] = row
            ch_lay.addWidget(row)
        lay.addWidget(self._grp_channels)

        # 删除按钮
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self._btn_del = QtWidgets.QPushButton("Delete This Definition")
        self._btn_del.setProperty("danger", True)
        self._btn_del.clicked.connect(lambda: self.removed.emit(self))
        btn_row.addWidget(self._btn_del)
        lay.addLayout(btn_row)

    # --- 序列化 (v2.0: name/format, 无 material_parameter/import_settings) ---
    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "enabled": self.w_enabled.value(),
            "name": self.w_name.value(),
            "suffix": self.w_suffix.value(),
            "category": self.w_category.value(),
            "srgb": self.w_srgb.value(),
            "format": self.w_format.value(),
            "bit_depth": int(self.w_bits.value()),
            "mips": self.w_mips.value(),
            "alpha_premultiplied": self.w_alpha_pre.value(),
            "allow_missing": self.w_allow_missing.value(),
            "flip_green": self.w_flip_green.value(),
        }
        ns = self.w_normal_space.value()
        if ns:
            d["normal_space"] = ns
        d["channels"] = {ch: row.to_dict() for ch, row in self.ch_rows.items()}
        return d

    def from_dict(self, d: dict) -> None:
        self.w_enabled.set_value(d.get("enabled", True))
        self.w_name.set_value(d.get("name", ""))
        self.w_suffix.set_value(d.get("suffix", ""))
        self.w_category.set_value(d.get("category", "PBR"))
        self.w_srgb.set_value(d.get("srgb", True))
        self.w_format.set_value(d.get("format", "PNG"))
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

    def update_title(self, index: int) -> None:
        name = self.w_name.value() or f"#{index + 1}"
        self.setTitle(f"#{index + 1}  {name}")

    def retranslate(self) -> None:
        """Update all translatable texts in this card."""
        self.w_enabled.check.setText(_t("def_enabled"))
        self.w_enabled.check.setToolTip(_t("def_enabled_tip"))
        self.w_name._lbl.setText(_t("def_name"))
        self.w_name._lbl.setToolTip(_t("def_name_tip"))
        self.w_name.edit.setToolTip(_t("def_name_tip"))
        self.w_suffix._lbl.setText(_t("def_suffix"))
        self.w_suffix._lbl.setToolTip(_t("def_suffix_tip"))
        self.w_suffix.edit.setToolTip(_t("def_suffix_tip"))
        self.w_category._lbl.setText(_t("def_category"))
        self.w_category._lbl.setToolTip(_t("def_category_tip"))
        self.w_category.edit.setToolTip(_t("def_category_tip"))
        self.w_srgb.check.setText(_t("def_srgb"))
        self.w_format._lbl.setText(_t("def_format"))
        self.w_bits._lbl.setText(_t("def_bits"))
        self.w_mips.check.setText(_t("def_mips"))
        self.w_allow_missing.check.setText(_t("def_allow_miss"))
        self.w_allow_missing.check.setToolTip(_t("def_allow_miss_tip"))
        self.w_flip_green.check.setText(_t("def_flip_g"))
        self.w_flip_green.check.setToolTip(_t("def_flip_g_tip"))
        self.w_alpha_pre.check.setText(_t("def_alpha_pre"))
        self.w_normal_space._lbl.setText(_t("def_normal_sp"))
        self._grp_channels.setTitle(_t("grp_channels"))
        self._btn_del.setText(_t("btn_del_def"))
        for row in self.ch_rows.values():
            row.retranslate()


# ===========================================================================
# 输入规则编辑（input.texture.rules 表格）
# ===========================================================================

class InputRulesTable(QtWidgets.QWidget):
    """输入规则的可增删表格。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QHBoxLayout()
        self._hdr_lbl = QtWidgets.QLabel("Texture Input Rules")
        header.addWidget(self._hdr_lbl)
        header.addStretch()
        self._btn_add = QtWidgets.QPushButton("+ Add Rule")
        self._btn_add.setProperty("secondary", True)
        self._btn_add.clicked.connect(self._on_add_rule)
        header.addWidget(self._btn_add)
        lay.addLayout(header)

        self._table = QtWidgets.QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Priority", "Patterns (comma-separated)"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 130)
        self._table.setColumnWidth(1, 60)
        self._table.verticalHeader().setVisible(False)
        lay.addWidget(self._table)

        self._btn_del = QtWidgets.QPushButton("Delete Selected Rule")
        self._btn_del.setProperty("danger", True)
        self._btn_del.clicked.connect(self._on_del_rule)
        lay.addWidget(self._btn_del)

    def retranslate(self) -> None:
        self._hdr_lbl.setText(_t("input_rules_hdr"))
        self._btn_add.setText(_t("btn_add_rule"))
        self._btn_del.setText(_t("btn_del_rule"))
        self._table.setHorizontalHeaderLabels([_t("col_name"), _t("col_priority"), _t("col_patterns")])

    def _on_add_rule(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, _t("dlg_add_rule"), _t("dlg_add_rule_p"))
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
    """AssetCustoms 图形化配置编辑器（v2.0 三段式）。"""

    def __init__(self, config_dir: str | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AssetCustoms Config Editor")
        self.resize(1060, 760)

        self._config_dir = config_dir or ""
        self._current_file: str = ""
        self._output_cards: list[OutputDefCard] = []
        self._override_cards: list[ImportOverrideCard] = []
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
        self._lbl_config = QtWidgets.QLabel("Config:")
        toolbar.addWidget(self._lbl_config)
        self._combo_file = NoScrollComboBox()
        self._combo_file.setMinimumWidth(200)
        self._combo_file.currentIndexChanged.connect(self._on_file_combo_changed)
        toolbar.addWidget(self._combo_file, 1)

        self._btn_new = QtWidgets.QPushButton("New")
        self._btn_new.setToolTip("Create a new config file")
        self._btn_new.setProperty("secondary", True)
        self._btn_new.clicked.connect(self._on_new_config)
        toolbar.addWidget(self._btn_new)

        self._btn_dup = QtWidgets.QPushButton("Duplicate")
        self._btn_dup.setToolTip("Duplicate currently loaded config")
        self._btn_dup.setProperty("secondary", True)
        self._btn_dup.clicked.connect(self._on_duplicate_config)
        toolbar.addWidget(self._btn_dup)

        self._btn_del = QtWidgets.QPushButton("Delete")
        self._btn_del.setToolTip("Delete selected config file")
        self._btn_del.setProperty("danger", True)
        self._btn_del.clicked.connect(self._on_delete_config)
        toolbar.addWidget(self._btn_del)

        self._btn_reload = QtWidgets.QPushButton("Reload")
        self._btn_reload.setToolTip("Reload from disk")
        self._btn_reload.setProperty("secondary", True)
        self._btn_reload.clicked.connect(self._on_reload)
        toolbar.addWidget(self._btn_reload)

        self._btn_save = QtWidgets.QPushButton("💾 Save")
        self._btn_save.setToolTip("Save to disk (Ctrl+S)")
        self._btn_save.clicked.connect(self._on_save)
        toolbar.addWidget(self._btn_save)

        self._btn_refresh = QtWidgets.QPushButton("↻ Refresh Menu")
        self._btn_refresh.setToolTip("Refresh the import preset dropdown in Content Browser")
        self._btn_refresh.setProperty("secondary", True)
        self._btn_refresh.clicked.connect(self._on_refresh_import_menu)
        toolbar.addWidget(self._btn_refresh)

        # 语言切换按钮
        self._btn_lang = QtWidgets.QPushButton("中文")
        self._btn_lang.setFixedWidth(60)
        self._btn_lang.setProperty("secondary", True)
        self._btn_lang.setToolTip("Switch language / 切换语言")
        self._btn_lang.clicked.connect(self._on_switch_lang)
        toolbar.addWidget(self._btn_lang)

        root.addLayout(toolbar)

        # ---- Tab 区域 (v2.0 三段式) ----
        self._tabs = QtWidgets.QTabWidget()
        root.addWidget(self._tabs, 1)

        # Tab 1: 输入（Input）
        self._tab_input = self._build_input_tab()
        self._tabs.addTab(self._tab_input, "Input")

        # Tab 2: 处理（Processing）
        self._tab_processing = self._build_processing_tab()
        self._tabs.addTab(self._tab_processing, "Processing")

        # Tab 3: 交付（Output）
        self._tab_output = self._build_output_tab()
        self._tabs.addTab(self._tab_output, "Output")

        # ---- 底部状态栏 ----
        self._statusbar = QtWidgets.QLabel("Ready")
        self._statusbar.setStyleSheet(
            "background: #007ACC; color: white; padding: 3px 8px; font-size: 11px; border-radius: 2px;")
        self._statusbar.setFixedHeight(24)
        root.addWidget(self._statusbar)

        # 快捷键
        save_sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        save_sc.activated.connect(self._on_save)

    # ------ Tab 1: Input ------
    def _build_input_tab(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setSpacing(6)

        g = QtWidgets.QGroupBox("Match Settings")
        self._grp_match = g
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

    # ------ Tab 2: Processing ------
    def _build_processing_tab(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setSpacing(6)

        # 冲突策略
        g_conflict = QtWidgets.QGroupBox("Processing Policy")
        self._grp_conflict = g_conflict
        g_lay = QtWidgets.QVBoxLayout(g_conflict)
        self.w_conflict = LabeledCombo(
            "Conflict Policy", CONFLICT_POLICIES, "version", "命名冲突策略")
        g_lay.addWidget(self.w_conflict)
        lay.addWidget(g_conflict)

        # 添加定义按钮
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_add_def = QtWidgets.QPushButton("+ Add Definition")
        self._btn_add_def.setProperty("secondary", True)
        self._btn_add_def.clicked.connect(self._on_add_output)
        btn_row.addWidget(self._btn_add_def)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # 定义卡片滚动区域
        self._output_scroll = QtWidgets.QScrollArea()
        self._output_scroll.setWidgetResizable(True)
        self._output_container = QtWidgets.QWidget()
        self._output_layout = QtWidgets.QVBoxLayout(self._output_container)
        self._output_layout.setSpacing(8)
        self._output_layout.addStretch()
        self._output_scroll.setWidget(self._output_container)
        lay.addWidget(self._output_scroll, 1)

        scroll.setWidget(w)
        return scroll

    def _on_skeletal_toggled(self, checked: bool) -> None:
        """import_as_skeletal 切换时显隐 Static/Skeletal 专有控件组。"""
        self._static_mesh_group.setVisible(not checked)
        self._skeletal_mesh_group.setVisible(checked)

    # ------ Tab 3: Output ------
    def _build_output_tab(self) -> QtWidgets.QWidget:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(content)
        lay.setSpacing(6)

        # 路径
        g_paths = QtWidgets.QGroupBox("Paths")
        self._grp_paths = g_paths
        g_paths_lay = QtWidgets.QVBoxLayout(g_paths)
        self.w_target_tpl = LabeledLine(
            "Target Path Template", "",
            _t("target_tpl_tip"))
        self.w_target_tpl.edit.setPlaceholderText(_t("target_tpl_ph"))
        g_paths_lay.addWidget(self.w_target_tpl)
        self.w_fallback_path = LabeledLine(
            "Fallback Import Path", "/Game/AIGC_Dropoff",
            _t("fallback_path_tip"))
        g_paths_lay.addWidget(self.w_fallback_path)
        lay.addWidget(g_paths)

        # 命名模板
        g_naming = QtWidgets.QGroupBox("Asset Naming Templates")
        self._grp_naming = g_naming
        g_naming_lay = QtWidgets.QVBoxLayout(g_naming)
        self.w_nm_sm = LabeledLine("Static Mesh", "SM_{Name}", _t("nm_sm_tip"))
        g_naming_lay.addWidget(self.w_nm_sm)
        self.w_nm_mi = LabeledLine("Material Instance", "MI_{Name}", _t("nm_mi_tip"))
        g_naming_lay.addWidget(self.w_nm_mi)
        self.w_nm_tex = LabeledLine("Texture", "T_{Name}_{Suffix}", _t("nm_tex_tip"))
        g_naming_lay.addWidget(self.w_nm_tex)
        lay.addWidget(g_naming)

        # 子目录
        g_subdirs = QtWidgets.QGroupBox("Asset Subdirectories")
        self._grp_subdirs = g_subdirs
        g_subdirs_lay = QtWidgets.QVBoxLayout(g_subdirs)
        self.w_subdir_mode = LabeledCombo(
            "Layout Mode",
            [_t("subdir_aggregated"), _t("subdir_separate")],
            _t("subdir_aggregated"),
            _t("subdir_mode_tip"))
        self.w_subdir_mode.combo.currentIndexChanged.connect(self._on_subdir_mode_changed)
        g_subdirs_lay.addWidget(self.w_subdir_mode)
        self.w_subdir_sm = LabeledLine(
            "Static Mesh Subdir", "", _t("subdir_sm_tip"))
        g_subdirs_lay.addWidget(self.w_subdir_sm)
        self.w_subdir_mi = LabeledLine(
            "Material Instance Subdir", "Materials", _t("subdir_mi_tip"))
        g_subdirs_lay.addWidget(self.w_subdir_mi)
        self.w_subdir_tex = LabeledLine(
            "Texture Subdir", "Textures", _t("subdir_tex_tip"))
        g_subdirs_lay.addWidget(self.w_subdir_tex)
        lay.addWidget(g_subdirs)

        # ── 模型导入设置（ADR-0003）──
        g_mesh = QtWidgets.QGroupBox("Mesh Import Settings")
        self._grp_mesh_import = g_mesh
        g_mesh.setCheckable(False)
        gm = QtWidgets.QVBoxLayout(g_mesh)

        # 基础
        self.w_mi_scale = LabeledFloat(
            "Uniform Scale", 1.0, minimum=0.0001, maximum=10000.0,
            decimals=4, tooltip="导入统一缩放")
        gm.addWidget(self.w_mi_scale)
        self.w_mi_skeletal = LabeledCheck("Import as Skeletal", False, "作为骨骼网格导入")
        gm.addWidget(self.w_mi_skeletal)

        # 法线与切线
        self.w_mi_normal_import = LabeledCombo(
            "Normal Import Method", NORMAL_IMPORT_METHODS, "ImportNormalsAndTangents", "法线导入方式")
        gm.addWidget(self.w_mi_normal_import)
        self.w_mi_normal_gen = LabeledCombo(
            "Normal Generation", NORMAL_GEN_METHODS, "MikkTSpace", "法线生成方式")
        gm.addWidget(self.w_mi_normal_gen)
        self.w_mi_weighted_normals = LabeledCheck("Compute Weighted Normals", True, "计算加权法线")
        gm.addWidget(self.w_mi_weighted_normals)

        # 顶点色
        self.w_mi_vertex_color = LabeledCombo(
            "Vertex Color Import", VERTEX_COLOR_OPTIONS, "Replace", "顶点色导入方式")
        gm.addWidget(self.w_mi_vertex_color)

        # 动画
        self.w_mi_animations = LabeledCheck("Import Animations", False, "导入动画")
        gm.addWidget(self.w_mi_animations)

        # 碰撞与几何（StaticMesh 专有）
        self._static_mesh_group = QtWidgets.QWidget()
        sm_lay = QtWidgets.QVBoxLayout(self._static_mesh_group)
        sm_lay.setContentsMargins(0, 0, 0, 0)
        sm_lay.setSpacing(6)
        self.w_mi_collision = LabeledCheck("Auto Generate Collision", True, "自动生成碰撞")
        sm_lay.addWidget(self.w_mi_collision)
        self.w_mi_combine = LabeledCheck("Combine Meshes", True, "合并网格")
        sm_lay.addWidget(self.w_mi_combine)
        self.w_mi_degenerates = LabeledCheck("Remove Degenerates", True, "移除退化三角形")
        sm_lay.addWidget(self.w_mi_degenerates)
        self.w_mi_nanite = LabeledCheck("Build Nanite", False, "构建 Nanite")
        sm_lay.addWidget(self.w_mi_nanite)
        self.w_mi_rev_idx = LabeledCheck("Build Reversed Index Buffer", True, "构建反向索引缓冲")
        sm_lay.addWidget(self.w_mi_rev_idx)
        self.w_mi_lightmap = LabeledCheck("Generate Lightmap UVs", True, "生成光照贴图 UV")
        sm_lay.addWidget(self.w_mi_lightmap)
        self.w_mi_lod_group = LabeledCombo(
            "Static Mesh LOD Group", MESH_LOD_GROUPS, "None", "静态网格 LOD 组")
        sm_lay.addWidget(self.w_mi_lod_group)
        self.w_mi_reorder_mat = LabeledCheck("Reorder Material to FBX Order", True, "按 FBX 顺序排列材质")
        sm_lay.addWidget(self.w_mi_reorder_mat)
        gm.addWidget(self._static_mesh_group)

        # SkeletalMesh 专有
        self._skeletal_mesh_group = QtWidgets.QWidget()
        sk_lay = QtWidgets.QVBoxLayout(self._skeletal_mesh_group)
        sk_lay.setContentsMargins(0, 0, 0, 0)
        sk_lay.setSpacing(6)
        self.w_mi_skeleton_path = LabeledLine("Skeleton Asset", "", "骨骼资产路径")
        sk_lay.addWidget(self.w_mi_skeleton_path)
        self.w_mi_create_phys = LabeledCheck("Create Physics Asset", True, "创建物理资产")
        sk_lay.addWidget(self.w_mi_create_phys)
        self.w_mi_morph_targets = LabeledCheck("Import Morph Targets", True, "导入变形目标")
        sk_lay.addWidget(self.w_mi_morph_targets)
        self.w_mi_bone_hierarchy = LabeledCheck("Import Meshes in Bone Hierarchy", True, "导入骨骼层级中的网格")
        sk_lay.addWidget(self.w_mi_bone_hierarchy)
        self.w_mi_update_ref_pose = LabeledCheck("Update Skeleton Reference Pose", False, "更新骨骼参考姿势")
        sk_lay.addWidget(self.w_mi_update_ref_pose)
        self.w_mi_t0_ref_pose = LabeledCheck("Use T0 as Reference Pose", False, "使用 T0 作为参考姿势")
        sk_lay.addWidget(self.w_mi_t0_ref_pose)
        self.w_mi_preserve_smooth = LabeledCheck("Preserve Smoothing Groups", True, "保留平滑组")
        sk_lay.addWidget(self.w_mi_preserve_smooth)
        self.w_mi_content_type = LabeledCombo(
            "Import Content Type", IMPORT_CONTENT_TYPES, "All", "导入内容类型")
        sk_lay.addWidget(self.w_mi_content_type)
        self._skeletal_mesh_group.setVisible(False)
        gm.addWidget(self._skeletal_mesh_group)

        # 动态显隐：import_as_skeletal 切换
        self.w_mi_skeletal.check.toggled.connect(self._on_skeletal_toggled)

        # 坐标变换
        self.w_mi_convert_scene = LabeledCheck("Convert Scene", True, "转换场景")
        gm.addWidget(self.w_mi_convert_scene)
        self.w_mi_convert_unit = LabeledCheck("Convert Scene Unit", True, "转换场景单位")
        gm.addWidget(self.w_mi_convert_unit)
        self.w_mi_force_front_x = LabeledCheck("Force Front X Axis", False, "强制前方为 X 轴")
        gm.addWidget(self.w_mi_force_front_x)

        # LOD
        self.w_mi_lods = LabeledCheck("Import Mesh LODs", False, "导入网格 LOD")
        gm.addWidget(self.w_mi_lods)

        # 材质/贴图导入
        self.w_mi_import_mat = LabeledCheck("Import Materials", True, "导入材质")
        gm.addWidget(self.w_mi_import_mat)
        self.w_mi_import_tex = LabeledCheck("Import Textures", True, "导入贴图")
        gm.addWidget(self.w_mi_import_tex)

        lay.addWidget(g_mesh)

        # 材质
        g_mat = QtWidgets.QGroupBox("Material")
        self._grp_material = g_mat
        g_mat_lay = QtWidgets.QVBoxLayout(g_mat)
        self.w_master_mat = LabeledLine(
            "Master Material", "", _t("master_mat_tip"))
        g_mat_lay.addWidget(self.w_master_mat)
        self._param_bindings = ParameterBindingsTable()
        g_mat_lay.addWidget(self._param_bindings)
        lay.addWidget(g_mat)

        # 导入默认值
        g_imp = QtWidgets.QGroupBox("Texture Import Defaults")
        self._grp_import_defaults = g_imp
        g_imp_lay = QtWidgets.QVBoxLayout(g_imp)
        self.w_imp_compression = LabeledCombo(
            "Compression", COMPRESSIONS, "TC_Default", editable=True)
        g_imp_lay.addWidget(self.w_imp_compression)
        self.w_imp_lod_group = LabeledCombo(
            "LOD Group", LOD_GROUPS, "TEXTUREGROUP_World", editable=True)
        g_imp_lay.addWidget(self.w_imp_lod_group)
        imp_row = QtWidgets.QHBoxLayout()
        self.w_imp_vt = LabeledCheck("Virtual Texture", False)
        imp_row.addWidget(self.w_imp_vt)
        self.w_imp_addr_x = LabeledCombo("Address X", ADDRESS_MODES, "Wrap")
        imp_row.addWidget(self.w_imp_addr_x)
        self.w_imp_addr_y = LabeledCombo("Address Y", ADDRESS_MODES, "Wrap")
        imp_row.addWidget(self.w_imp_addr_y)
        self.w_imp_mipgen = LabeledCombo("Mip Gen", MIP_GEN_MODES, "FromTextureGroup")
        imp_row.addWidget(self.w_imp_mipgen)
        g_imp_lay.addLayout(imp_row)
        lay.addWidget(g_imp)

        # 导入覆盖
        g_ovr = QtWidgets.QGroupBox("Texture Import Overrides (per-suffix)")
        self._grp_import_overrides = g_ovr
        g_ovr_lay = QtWidgets.QVBoxLayout(g_ovr)
        ovr_btn_row = QtWidgets.QHBoxLayout()
        self._btn_add_override = QtWidgets.QPushButton("+ Add Override")
        self._btn_add_override.setProperty("secondary", True)
        self._btn_add_override.clicked.connect(self._on_add_override)
        ovr_btn_row.addWidget(self._btn_add_override)
        ovr_btn_row.addStretch()
        g_ovr_lay.addLayout(ovr_btn_row)
        self._override_container = QtWidgets.QVBoxLayout()
        g_ovr_lay.addLayout(self._override_container)
        lay.addWidget(g_ovr)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

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
            self, _t("dlg_new"), _t("dlg_new_p"))
        if not ok or not name.strip():
            return
        name = name.strip()
        path = os.path.join(self._config_dir, f"{name}.jsonc")
        if os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, _t("dlg_exists"), _t("dlg_exists_p", n=f"{name}.jsonc"))
            return
        default_data: dict[str, Any] = {
            "config_version": "2.0",
            "input": {
                "texture": {
                    "match_mode": "glob",
                    "ignore_case": True,
                    "extensions": [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"],
                    "search_roots": ["{DropDir}", "{DropDir}/Textures", "{DropDir}/Maps"],
                    "rules": {},
                },
            },
            "processing": {
                "conflict_policy": "version",
                "mesh_import": {
                    "import_uniform_scale": 1.0,
                    "import_as_skeletal": False,
                    "normal_import_method": "ImportNormalsAndTangents",
                    "normal_generation_method": "MikkTSpace",
                    "compute_weighted_normals": True,
                    "vertex_color_import_option": "Replace",
                    "import_animations": False,
                    "auto_generate_collision": True,
                    "combine_meshes": True,
                    "remove_degenerates": True,
                    "build_nanite": False,
                    "build_reversed_index_buffer": True,
                    "generate_lightmap_u_vs": True,
                    "convert_scene": True,
                    "convert_scene_unit": True,
                    "force_front_x_axis": False,
                    "import_mesh_lods": False,
                    "static_mesh_lod_group": "None",
                    "import_materials": True,
                    "import_textures": True,
                    "reorder_material_to_fbx_order": True,
                    # SkeletalMesh 专有
                    "skeleton_path": "",
                    "create_physics_asset": True,
                    "import_morph_targets": True,
                    "import_meshes_in_bone_hierarchy": True,
                    "update_skeleton_reference_pose": False,
                    "use_t0_as_ref_pose": False,
                    "preserve_smoothing_groups": True,
                    "import_content_type": "All",
                },
                "texture_definitions": [],
            },
            "output": {
                "target_path_template": "/Game/Assets/{Category}/{Name}",
                "fallback_path": "/Game/AIGC_Dropoff",
                "subdirectories": {
                    "static_mesh": "",
                    "material_instance": "",
                    "texture": "",
                },
                "naming": {
                    "static_mesh": "SM_{Name}",
                    "material_instance": "MI_{Name}",
                    "texture": "T_{Name}_{Suffix}",
                },
                "material": {
                    "master_material_path": "",
                    "parameter_bindings": {},
                },
                "texture_import_defaults": {
                    "compression": "TC_Default",
                    "lod_group": "TEXTUREGROUP_World",
                    "virtual_texture": False,
                    "address_x": "Wrap",
                    "address_y": "Wrap",
                    "mip_gen": "FromTextureGroup",
                },
                "texture_import_overrides": {},
            },
        }
        _save_jsonc(path, default_data)
        self._refresh_file_combo()
        idx = self._combo_file.findText(f"{name}.jsonc")
        if idx >= 0:
            self._combo_file.setCurrentIndex(idx)
        self._statusbar.setText(_t("st_created", n=f"{name}.jsonc"))
        self._on_refresh_import_menu()

    def _on_duplicate_config(self) -> None:
        if not self._current_file:
            return
        base = os.path.splitext(os.path.basename(self._current_file))[0]
        name, ok = QtWidgets.QInputDialog.getText(
            self, _t("dlg_dup"), _t("dlg_dup_p"), text=f"{base}_copy")
        if not ok or not name.strip():
            return
        name = name.strip()
        dest = os.path.join(self._config_dir, f"{name}.jsonc")
        if os.path.exists(dest):
            QtWidgets.QMessageBox.warning(self, _t("dlg_exists"), _t("dlg_exists_p", n=f"{name}.jsonc"))
            return
        data = self._collect_data()
        _save_jsonc(dest, data)
        self._refresh_file_combo()
        idx = self._combo_file.findText(f"{name}.jsonc")
        if idx >= 0:
            self._combo_file.setCurrentIndex(idx)
        self._statusbar.setText(_t("st_duplicated", n=f"{name}.jsonc"))
        self._on_refresh_import_menu()

    def _on_delete_config(self) -> None:
        if not self._current_file:
            return
        fn = os.path.basename(self._current_file)
        reply = QtWidgets.QMessageBox.warning(
            self, _t("dlg_del"),
            _t("dlg_del_p", n=fn),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(self._current_file)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, _t("dlg_error"), _t("dlg_del_fail", e=ex))
            return
        self._current_file = ""
        self._refresh_file_combo()
        self._statusbar.setText(_t("st_deleted", n=fn))
        self._on_refresh_import_menu()

    def _on_reload(self) -> None:
        if self._current_file:
            self._load_config(self._current_file)

    def _on_save(self) -> None:
        if not self._current_file:
            self._statusbar.setText(_t("st_no_file"))
            return
        data = self._collect_data()
        try:
            _save_jsonc(self._current_file, data)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, _t("dlg_error"), _t("dlg_save_fail", e=ex))
            return
        self._statusbar.setText(_t("st_saved", n=os.path.basename(self._current_file)))
        self._on_refresh_import_menu()

    # ------------------------------------------------------------------
    # Load / Collect (v2.0 三段式)
    # ------------------------------------------------------------------
    def _load_config(self, path: str) -> None:
        try:
            data = _load_jsonc(path)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, _t("dlg_error"), _t("dlg_load_fail", e=ex))
            return

        self._loading = True
        self._current_file = path

        # --- Input ---
        inp = data.get("input", {})
        tex_inp = inp.get("texture", {})
        self.w_match_mode.set_value(tex_inp.get("match_mode", "glob"))
        self.w_ignore_case.set_value(tex_inp.get("ignore_case", True))
        self.w_extensions.set_values(tex_inp.get("extensions",
                                                  [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"]))
        self.w_search_roots.set_values(tex_inp.get("search_roots",
                                                    ["{DropDir}", "{DropDir}/Textures", "{DropDir}/Maps"]))
        self._input_rules_table.from_dict(tex_inp.get("rules", {}))

        # --- Processing ---
        proc = data.get("processing", {})
        self.w_conflict.set_value(proc.get("conflict_policy", "version"))

        # Mesh Import
        mi = proc.get("mesh_import", {})
        self.w_mi_scale.set_value(mi.get("import_uniform_scale", 1.0))
        self.w_mi_skeletal.set_value(mi.get("import_as_skeletal", False))
        self.w_mi_normal_import.set_value(mi.get("normal_import_method", "ImportNormalsAndTangents"))
        self.w_mi_normal_gen.set_value(mi.get("normal_generation_method", "MikkTSpace"))
        self.w_mi_weighted_normals.set_value(mi.get("compute_weighted_normals", True))
        self.w_mi_vertex_color.set_value(mi.get("vertex_color_import_option", "Replace"))
        self.w_mi_animations.set_value(mi.get("import_animations", False))
        self.w_mi_collision.set_value(mi.get("auto_generate_collision", True))
        self.w_mi_combine.set_value(mi.get("combine_meshes", True))
        self.w_mi_degenerates.set_value(mi.get("remove_degenerates", True))
        self.w_mi_nanite.set_value(mi.get("build_nanite", False))
        self.w_mi_rev_idx.set_value(mi.get("build_reversed_index_buffer", True))
        self.w_mi_lightmap.set_value(mi.get("generate_lightmap_u_vs", True))
        self.w_mi_convert_scene.set_value(mi.get("convert_scene", True))
        self.w_mi_convert_unit.set_value(mi.get("convert_scene_unit", True))
        self.w_mi_force_front_x.set_value(mi.get("force_front_x_axis", False))
        self.w_mi_lods.set_value(mi.get("import_mesh_lods", False))
        self.w_mi_lod_group.set_value(mi.get("static_mesh_lod_group", "None"))
        self.w_mi_import_mat.set_value(mi.get("import_materials", True))
        self.w_mi_import_tex.set_value(mi.get("import_textures", True))
        self.w_mi_reorder_mat.set_value(mi.get("reorder_material_to_fbx_order", True))
        # SkeletalMesh 专有
        self.w_mi_skeleton_path.set_value(mi.get("skeleton_path", ""))
        self.w_mi_create_phys.set_value(mi.get("create_physics_asset", True))
        self.w_mi_morph_targets.set_value(mi.get("import_morph_targets", True))
        self.w_mi_bone_hierarchy.set_value(mi.get("import_meshes_in_bone_hierarchy", True))
        self.w_mi_update_ref_pose.set_value(mi.get("update_skeleton_reference_pose", False))
        self.w_mi_t0_ref_pose.set_value(mi.get("use_t0_as_ref_pose", False))
        self.w_mi_preserve_smooth.set_value(mi.get("preserve_smoothing_groups", True))
        self.w_mi_content_type.set_value(mi.get("import_content_type", "All"))
        # 触发显隐同步
        self._on_skeletal_toggled(mi.get("import_as_skeletal", False))

        self._clear_output_cards()
        for td in proc.get("texture_definitions", []):
            card = self._add_output_card()
            card.from_dict(td)
        self._renumber_output_cards()

        # --- Output ---
        out = data.get("output", {})
        self.w_target_tpl.set_value(out.get("target_path_template", ""))
        self.w_fallback_path.set_value(out.get("fallback_path", "/Game/AIGC_Dropoff"))

        naming = out.get("naming", {})
        self.w_nm_sm.set_value(naming.get("static_mesh", "SM_{Name}"))
        self.w_nm_mi.set_value(naming.get("material_instance", "MI_{Name}"))
        self.w_nm_tex.set_value(naming.get("texture", "T_{Name}_{Suffix}"))

        subdirs = out.get("subdirectories", {})
        sm_val = subdirs.get("static_mesh", "")
        mi_val = subdirs.get("material_instance", "")
        tex_val = subdirs.get("texture", "")
        has_subdirs = bool(sm_val or mi_val or tex_val)
        self.w_subdir_mode.combo.setCurrentIndex(1 if has_subdirs else 0)
        self.w_subdir_sm.set_value(sm_val)
        self.w_subdir_mi.set_value(mi_val)
        self.w_subdir_tex.set_value(tex_val)
        self._on_subdir_mode_changed(1 if has_subdirs else 0)

        mat = out.get("material", {})
        self.w_master_mat.set_value(mat.get("master_material_path", ""))
        self._param_bindings.from_dict(mat.get("parameter_bindings", {}))

        imp_def = out.get("texture_import_defaults", {})
        self.w_imp_compression.set_value(imp_def.get("compression", "TC_Default"))
        self.w_imp_lod_group.set_value(imp_def.get("lod_group", "TEXTUREGROUP_World"))
        self.w_imp_vt.set_value(imp_def.get("virtual_texture", False))
        self.w_imp_addr_x.set_value(imp_def.get("address_x", "Wrap"))
        self.w_imp_addr_y.set_value(imp_def.get("address_y", "Wrap"))
        self.w_imp_mipgen.set_value(imp_def.get("mip_gen", "FromTextureGroup"))

        self._clear_override_cards()
        for suffix, ovr_d in out.get("texture_import_overrides", {}).items():
            self._add_override_card(suffix, ovr_d)

        self._loading = False
        self._statusbar.setText(_t("st_loaded", n=os.path.basename(path)))

    def _collect_data(self) -> dict:
        """从表单控件收集完整配置 dict（v2.0 三段式）。"""
        # Build import overrides dict
        overrides: dict[str, dict] = {}
        for card in self._override_cards:
            suffix, d = card.to_tuple()
            if suffix and d:
                overrides[suffix] = d

        data: dict[str, Any] = {
            "config_version": "2.0",
            "input": {
                "texture": {
                    "match_mode": self.w_match_mode.value(),
                    "ignore_case": self.w_ignore_case.value(),
                    "extensions": self.w_extensions.values(),
                    "search_roots": self.w_search_roots.values(),
                    "rules": self._input_rules_table.to_dict(),
                },
            },
            "processing": {
                "conflict_policy": self.w_conflict.value(),
                "mesh_import": {
                    "import_uniform_scale": self.w_mi_scale.value(),
                    "import_as_skeletal": self.w_mi_skeletal.value(),
                    "normal_import_method": self.w_mi_normal_import.value(),
                    "normal_generation_method": self.w_mi_normal_gen.value(),
                    "compute_weighted_normals": self.w_mi_weighted_normals.value(),
                    "vertex_color_import_option": self.w_mi_vertex_color.value(),
                    "import_animations": self.w_mi_animations.value(),
                    "auto_generate_collision": self.w_mi_collision.value(),
                    "combine_meshes": self.w_mi_combine.value(),
                    "remove_degenerates": self.w_mi_degenerates.value(),
                    "build_nanite": self.w_mi_nanite.value(),
                    "build_reversed_index_buffer": self.w_mi_rev_idx.value(),
                    "generate_lightmap_u_vs": self.w_mi_lightmap.value(),
                    "convert_scene": self.w_mi_convert_scene.value(),
                    "convert_scene_unit": self.w_mi_convert_unit.value(),
                    "force_front_x_axis": self.w_mi_force_front_x.value(),
                    "import_mesh_lods": self.w_mi_lods.value(),
                    "static_mesh_lod_group": self.w_mi_lod_group.value(),
                    "import_materials": self.w_mi_import_mat.value(),
                    "import_textures": self.w_mi_import_tex.value(),
                    "reorder_material_to_fbx_order": self.w_mi_reorder_mat.value(),
                    # SkeletalMesh 专有
                    "skeleton_path": self.w_mi_skeleton_path.value(),
                    "create_physics_asset": self.w_mi_create_phys.value(),
                    "import_morph_targets": self.w_mi_morph_targets.value(),
                    "import_meshes_in_bone_hierarchy": self.w_mi_bone_hierarchy.value(),
                    "update_skeleton_reference_pose": self.w_mi_update_ref_pose.value(),
                    "use_t0_as_ref_pose": self.w_mi_t0_ref_pose.value(),
                    "preserve_smoothing_groups": self.w_mi_preserve_smooth.value(),
                    "import_content_type": self.w_mi_content_type.value(),
                },
                "texture_definitions": [c.to_dict() for c in self._output_cards],
            },
            "output": {
                "target_path_template": self.w_target_tpl.value(),
                "fallback_path": self.w_fallback_path.value(),
                "subdirectories": {
                    "static_mesh": self.w_subdir_sm.value() if self.w_subdir_mode.combo.currentIndex() == 1 else "",
                    "material_instance": self.w_subdir_mi.value() if self.w_subdir_mode.combo.currentIndex() == 1 else "",
                    "texture": self.w_subdir_tex.value() if self.w_subdir_mode.combo.currentIndex() == 1 else "",
                },
                "naming": {
                    "static_mesh": self.w_nm_sm.value(),
                    "material_instance": self.w_nm_mi.value(),
                    "texture": self.w_nm_tex.value(),
                },
                "material": {
                    "master_material_path": self.w_master_mat.value(),
                    "parameter_bindings": self._param_bindings.to_dict(),
                },
                "texture_import_defaults": {
                    "compression": self.w_imp_compression.value(),
                    "lod_group": self.w_imp_lod_group.value(),
                    "virtual_texture": self.w_imp_vt.value(),
                    "address_x": self.w_imp_addr_x.value(),
                    "address_y": self.w_imp_addr_y.value(),
                    "mip_gen": self.w_imp_mipgen.value(),
                },
                "texture_import_overrides": overrides,
            },
        }
        return data

    # ------------------------------------------------------------------
    # Subdirectory mode toggle
    # ------------------------------------------------------------------
    def _on_subdir_mode_changed(self, index: int) -> None:
        """Enable/disable subdirectory fields based on mode selection."""
        separate = index == 1
        self.w_subdir_sm.setEnabled(separate)
        self.w_subdir_mi.setEnabled(separate)
        self.w_subdir_tex.setEnabled(separate)
        if not separate and not self._loading:
            self.w_subdir_sm.set_value("")
            self.w_subdir_mi.set_value("")
            self.w_subdir_tex.set_value("")
        elif separate and not self._loading:
            if not self.w_subdir_mi.value():
                self.w_subdir_mi.set_value("Materials")
            if not self.w_subdir_tex.value():
                self.w_subdir_tex.set_value("Textures")

    # ------------------------------------------------------------------
    # Output cards management (texture definitions)
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
    # Import override cards management
    # ------------------------------------------------------------------
    def _add_override_card(self, suffix: str = "", data: dict | None = None) -> ImportOverrideCard:
        card = ImportOverrideCard(suffix)
        if data:
            card.from_data(suffix, data)
        card.removed.connect(self._on_remove_override)
        self._override_cards.append(card)
        self._override_container.addWidget(card)
        return card

    def _on_add_override(self) -> None:
        self._add_override_card()

    def _on_remove_override(self, card: ImportOverrideCard) -> None:
        if card in self._override_cards:
            self._override_cards.remove(card)
            card.setParent(None)
            card.deleteLater()

    def _clear_override_cards(self) -> None:
        for card in self._override_cards:
            card.setParent(None)
            card.deleteLater()
        self._override_cards.clear()

    # ------------------------------------------------------------------
    # Language switching
    # ------------------------------------------------------------------
    def _on_switch_lang(self) -> None:
        global _LANG
        _LANG = "zh" if _LANG == "en" else "en"
        self._retranslate()

    def _retranslate(self) -> None:
        """Refresh all translatable UI texts to the current language."""
        self.setWindowTitle(_t("window_title"))
        # Toolbar
        self._lbl_config.setText(_t("config_label"))
        self._btn_new.setText(_t("btn_new"))
        self._btn_new.setToolTip(_t("btn_new_tip"))
        self._btn_dup.setText(_t("btn_dup"))
        self._btn_dup.setToolTip(_t("btn_dup_tip"))
        self._btn_del.setText(_t("btn_del"))
        self._btn_del.setToolTip(_t("btn_del_tip"))
        self._btn_reload.setText(_t("btn_reload"))
        self._btn_reload.setToolTip(_t("btn_reload_tip"))
        self._btn_save.setText(_t("btn_save"))
        self._btn_save.setToolTip(_t("btn_save_tip"))
        self._btn_refresh.setText(_t("btn_refresh"))
        self._btn_refresh.setToolTip(_t("btn_refresh_tip"))
        self._btn_lang.setText("English" if _LANG == "zh" else "中文")
        # Tabs
        self._tabs.setTabText(0, _t("tab_input"))
        self._tabs.setTabText(1, _t("tab_processing"))
        self._tabs.setTabText(2, _t("tab_output"))
        # Input tab
        self._grp_match.setTitle(_t("grp_match"))
        self.w_match_mode._lbl.setText(_t("match_mode"))
        self.w_ignore_case.check.setText(_t("ignore_case"))
        self.w_extensions._title_lbl.setText(_t("extensions"))
        self.w_extensions._title_lbl.setToolTip(_t("extensions_tip"))
        self.w_search_roots._title_lbl.setText(_t("search_roots"))
        self.w_search_roots._title_lbl.setToolTip(_t("search_roots_tip"))
        self._input_rules_table.retranslate()
        # Processing tab
        self._grp_conflict.setTitle(_t("grp_conflict"))
        self.w_conflict._lbl.setText(_t("conflict"))
        self.w_conflict._lbl.setToolTip(_t("conflict_tip"))
        self._btn_add_def.setText(_t("btn_add_def"))
        # Mesh Import
        self._grp_mesh_import.setTitle(_t("grp_mesh_import"))
        self.w_mi_scale._lbl.setText(_t("mi_scale"))
        self.w_mi_scale._lbl.setToolTip(_t("mi_scale_tip"))
        self.w_mi_skeletal.check.setText(_t("mi_skeletal"))
        self.w_mi_skeletal.check.setToolTip(_t("mi_skeletal_tip"))
        self.w_mi_normal_import._lbl.setText(_t("mi_normal_import"))
        self.w_mi_normal_import._lbl.setToolTip(_t("mi_normal_import_tip"))
        self.w_mi_normal_gen._lbl.setText(_t("mi_normal_gen"))
        self.w_mi_normal_gen._lbl.setToolTip(_t("mi_normal_gen_tip"))
        self.w_mi_weighted_normals.check.setText(_t("mi_weighted_normals"))
        self.w_mi_weighted_normals.check.setToolTip(_t("mi_weighted_normals_tip"))
        self.w_mi_vertex_color._lbl.setText(_t("mi_vertex_color"))
        self.w_mi_vertex_color._lbl.setToolTip(_t("mi_vertex_color_tip"))
        self.w_mi_animations.check.setText(_t("mi_animations"))
        self.w_mi_animations.check.setToolTip(_t("mi_animations_tip"))
        self.w_mi_collision.check.setText(_t("mi_collision"))
        self.w_mi_collision.check.setToolTip(_t("mi_collision_tip"))
        self.w_mi_combine.check.setText(_t("mi_combine"))
        self.w_mi_combine.check.setToolTip(_t("mi_combine_tip"))
        self.w_mi_degenerates.check.setText(_t("mi_degenerates"))
        self.w_mi_degenerates.check.setToolTip(_t("mi_degenerates_tip"))
        self.w_mi_nanite.check.setText(_t("mi_nanite"))
        self.w_mi_nanite.check.setToolTip(_t("mi_nanite_tip"))
        self.w_mi_rev_idx.check.setText(_t("mi_rev_idx"))
        self.w_mi_rev_idx.check.setToolTip(_t("mi_rev_idx_tip"))
        self.w_mi_lightmap.check.setText(_t("mi_lightmap"))
        self.w_mi_lightmap.check.setToolTip(_t("mi_lightmap_tip"))
        self.w_mi_convert_scene.check.setText(_t("mi_convert_scene"))
        self.w_mi_convert_unit.check.setText(_t("mi_convert_unit"))
        self.w_mi_force_front_x.check.setText(_t("mi_force_front_x"))
        self.w_mi_lods.check.setText(_t("mi_lods"))
        self.w_mi_lods.check.setToolTip(_t("mi_lods_tip"))
        self.w_mi_lod_group._lbl.setText(_t("mi_lod_group"))
        self.w_mi_import_mat.check.setText(_t("mi_import_mat"))
        self.w_mi_import_mat.check.setToolTip(_t("mi_import_mat_tip"))
        self.w_mi_import_tex.check.setText(_t("mi_import_tex"))
        self.w_mi_import_tex.check.setToolTip(_t("mi_import_tex_tip"))
        self.w_mi_reorder_mat.check.setText(_t("mi_reorder_mat"))
        self.w_mi_reorder_mat.check.setToolTip(_t("mi_reorder_mat_tip"))
        # SkeletalMesh 专有
        self.w_mi_skeleton_path._lbl.setText(_t("mi_skeleton_path"))
        self.w_mi_skeleton_path._lbl.setToolTip(_t("mi_skeleton_path_tip"))
        self.w_mi_create_phys.check.setText(_t("mi_create_phys"))
        self.w_mi_create_phys.check.setToolTip(_t("mi_create_phys_tip"))
        self.w_mi_morph_targets.check.setText(_t("mi_morph_targets"))
        self.w_mi_morph_targets.check.setToolTip(_t("mi_morph_targets_tip"))
        self.w_mi_bone_hierarchy.check.setText(_t("mi_bone_hierarchy"))
        self.w_mi_bone_hierarchy.check.setToolTip(_t("mi_bone_hierarchy_tip"))
        self.w_mi_update_ref_pose.check.setText(_t("mi_update_ref_pose"))
        self.w_mi_update_ref_pose.check.setToolTip(_t("mi_update_ref_pose_tip"))
        self.w_mi_t0_ref_pose.check.setText(_t("mi_t0_ref_pose"))
        self.w_mi_t0_ref_pose.check.setToolTip(_t("mi_t0_ref_pose_tip"))
        self.w_mi_preserve_smooth.check.setText(_t("mi_preserve_smooth"))
        self.w_mi_preserve_smooth.check.setToolTip(_t("mi_preserve_smooth_tip"))
        self.w_mi_content_type._lbl.setText(_t("mi_content_type"))
        self.w_mi_content_type._lbl.setToolTip(_t("mi_content_type_tip"))
        for card in self._output_cards:
            card.retranslate()
        # Output tab
        self._grp_paths.setTitle(_t("grp_paths"))
        self.w_target_tpl._lbl.setText(_t("target_tpl"))
        self.w_target_tpl._lbl.setToolTip(_t("target_tpl_tip"))
        self.w_target_tpl.edit.setToolTip(_t("target_tpl_tip"))
        self.w_target_tpl.edit.setPlaceholderText(_t("target_tpl_ph"))
        self.w_fallback_path._lbl.setText(_t("fallback_path"))
        self.w_fallback_path._lbl.setToolTip(_t("fallback_path_tip"))
        self.w_fallback_path.edit.setToolTip(_t("fallback_path_tip"))
        self._grp_naming.setTitle(_t("grp_naming"))
        self.w_nm_sm._lbl.setText(_t("nm_sm"))
        self.w_nm_sm._lbl.setToolTip(_t("nm_sm_tip"))
        self.w_nm_mi._lbl.setText(_t("nm_mi"))
        self.w_nm_mi._lbl.setToolTip(_t("nm_mi_tip"))
        self.w_nm_tex._lbl.setText(_t("nm_tex"))
        self.w_nm_tex._lbl.setToolTip(_t("nm_tex_tip"))
        self._grp_subdirs.setTitle(_t("grp_subdirs"))
        self.w_subdir_mode._lbl.setText(_t("subdir_mode"))
        self.w_subdir_mode._lbl.setToolTip(_t("subdir_mode_tip"))
        self.w_subdir_mode.combo.setToolTip(_t("subdir_mode_tip"))
        self.w_subdir_mode.combo.setItemText(0, _t("subdir_aggregated"))
        self.w_subdir_mode.combo.setItemText(1, _t("subdir_separate"))
        self.w_subdir_sm._lbl.setText(_t("subdir_sm"))
        self.w_subdir_sm._lbl.setToolTip(_t("subdir_sm_tip"))
        self.w_subdir_sm.edit.setToolTip(_t("subdir_sm_tip"))
        self.w_subdir_mi._lbl.setText(_t("subdir_mi"))
        self.w_subdir_mi._lbl.setToolTip(_t("subdir_mi_tip"))
        self.w_subdir_mi.edit.setToolTip(_t("subdir_mi_tip"))
        self.w_subdir_tex._lbl.setText(_t("subdir_tex"))
        self.w_subdir_tex._lbl.setToolTip(_t("subdir_tex_tip"))
        self.w_subdir_tex.edit.setToolTip(_t("subdir_tex_tip"))
        self._grp_material.setTitle(_t("grp_material"))
        self.w_master_mat._lbl.setText(_t("master_mat"))
        self.w_master_mat._lbl.setToolTip(_t("master_mat_tip"))
        self.w_master_mat.edit.setToolTip(_t("master_mat_tip"))
        self._param_bindings.retranslate()
        self._grp_import_defaults.setTitle(_t("grp_import_defaults"))
        self.w_imp_compression._lbl.setText(_t("imp_compress"))
        self.w_imp_lod_group._lbl.setText(_t("imp_lod"))
        self.w_imp_vt.check.setText(_t("imp_vt"))
        self.w_imp_addr_x._lbl.setText(_t("imp_addr_x"))
        self.w_imp_addr_y._lbl.setText(_t("imp_addr_y"))
        self.w_imp_mipgen._lbl.setText(_t("imp_mipgen"))
        self._grp_import_overrides.setTitle(_t("grp_import_overrides"))
        self._btn_add_override.setText(_t("btn_add_override"))
        for ocard in self._override_cards:
            ocard.retranslate()
        # Status bar
        self._statusbar.setText(_t("st_ready"))

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
