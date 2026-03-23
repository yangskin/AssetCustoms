"""隔离区导入管道（FR2）+ 标准化编排器。

Unreal 集成层：编排导入 → 检查 → 标准化的完整流程。
UE API 调用集中于此模块，core 层保持纯 Python。
"""
from __future__ import annotations

import os
import logging
import copy
import time
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    import unreal  # type: ignore
except Exception:
    unreal = None

from core.config.schema import PluginConfig, TextureOutputDef
from core.naming import (
    ResolvedNames,
    compute_isolation_path,
    extract_base_name,
    resolve_conflict,
    resolve_names,
)
from core.pipeline.check_chain import CheckResult, CheckStatus, run_check_chain
from core.pipeline.standardize import ProcessedTexture, StandardizeResult, process_textures
from core.textures.matcher import MatchResult, discover_texture_files, match_textures

logger = logging.getLogger("AssetCustoms")

# NFR1: 性能预算阈值（秒）
_PERF_BUDGET_SECONDS = 5.0


@dataclass
class TriageContext:
    """保存 FR3 失败时的上下文，供 FR4 分诊后恢复 FR5 使用。"""
    config: Optional[PluginConfig] = None
    category: str = ""
    current_path: str = "/Game"
    base_name: str = ""
    embedded_lookup: Dict[str, str] = field(default_factory=dict)
    all_texture_paths: List[str] = field(default_factory=list)


@dataclass
class ImportPipelineResult:
    """完整导入管道的输出。"""
    phase: str = "init"               # 当前阶段："import" | "check" | "standardize" | "done"
    isolation_path: str = ""
    names: Optional[ResolvedNames] = None
    check_result: Optional[CheckResult] = None
    standardize_result: Optional[StandardizeResult] = None
    errors: List[str] = field(default_factory=list)
    triage_context: Optional[TriageContext] = None

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.phase == "done"


# ---------------------------------------------------------------------------
# UE 资产操作接口（可 mock 测试）
# ---------------------------------------------------------------------------

class UnrealAssetOps:
    """封装 Unreal 资产操作的接口类，便于测试时 mock。"""

    def import_fbx(
        self,
        fbx_path: str,
        destination_path: str,
        import_textures: bool = True,
    ) -> List[str]:
        """导入 FBX 到隔离区，返回导入后的资产名列表。"""
        if unreal is None:
            raise RuntimeError("Unreal 环境不可用")

        task = unreal.AssetImportTask()
        task.set_editor_property("filename", fbx_path)
        task.set_editor_property("destination_path", destination_path)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)

        # FBX 设置
        fbx_options = unreal.FbxImportUI()
        fbx_options.set_editor_property("import_mesh", True)
        fbx_options.set_editor_property("import_textures", import_textures)
        fbx_options.set_editor_property("import_materials", True)
        fbx_options.set_editor_property("import_as_skeletal", False)
        task.set_editor_property("options", fbx_options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        # 收集导入的资产
        imported = task.get_editor_property("imported_object_paths")
        return list(imported) if imported else []

    def asset_exists(self, asset_path: str) -> bool:
        """检查 UE 资产是否存在。"""
        if unreal is None:
            return False
        return unreal.EditorAssetLibrary.does_asset_exist(asset_path)

    def list_assets_in_path(self, path: str) -> List[str]:
        """列出路径下的所有资产。"""
        if unreal is None:
            return []
        return list(unreal.EditorAssetLibrary.list_assets(path, recursive=True))

    def rename_asset(self, source: str, destination: str) -> bool:
        """重命名/移动资产。"""
        if unreal is None:
            return False
        return unreal.EditorAssetLibrary.rename_asset(source, destination)

    def delete_directory(self, path: str) -> bool:
        """删除 UE 目录（隔离区清理）。"""
        if unreal is None:
            return False
        return unreal.EditorAssetLibrary.delete_directory(path)

    def create_material_instance(
        self,
        mi_path: str,
        parent_material_path: str,
    ) -> Any:
        """创建材质实例。"""
        if unreal is None:
            return None

        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        mi_dir = "/".join(mi_path.split("/")[:-1])
        mi_name = mi_path.split("/")[-1]

        factory = unreal.MaterialInstanceConstantFactoryNew()
        mi = asset_tools.create_asset(mi_name, mi_dir, unreal.MaterialInstanceConstant, factory)
        if mi is None:
            return None

        # 设置父材质
        parent = unreal.EditorAssetLibrary.load_asset(parent_material_path)
        if parent:
            mi.set_editor_property("parent", parent)
            unreal.EditorAssetLibrary.save_asset(mi_path)
        return mi

    def set_material_texture_param(self, mi: Any, param_name: str, texture_path: str) -> bool:
        """设置材质实例的纹理参数。"""
        if unreal is None or mi is None:
            return False
        tex = unreal.EditorAssetLibrary.load_asset(texture_path)
        if tex is None:
            return False
        return unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            mi, param_name, tex
        )

    def set_static_mesh_material(self, mesh_path: str, mi_path: str, slot: int = 0) -> bool:
        """设置 StaticMesh 的材质槽。"""
        if unreal is None:
            return False
        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
        mi = unreal.EditorAssetLibrary.load_asset(mi_path)
        if mesh is None or mi is None:
            return False
        mesh.set_material(slot, mi)
        unreal.EditorAssetLibrary.save_asset(mesh_path)
        return True

    def apply_texture_import_settings(self, texture_path: str, settings: Dict) -> bool:
        """应用纹理导入设置。"""
        if unreal is None:
            return False
        tex = unreal.EditorAssetLibrary.load_asset(texture_path)
        if tex is None:
            return False

        if "compression" in settings:
            compression_map = {
                "TC_Default": unreal.TextureCompressionSettings.TC_DEFAULT,
                "TC_Normalmap": unreal.TextureCompressionSettings.TC_NORMALMAP,
                "TC_Masks": unreal.TextureCompressionSettings.TC_MASKS,
                "TC_Grayscale": unreal.TextureCompressionSettings.TC_GRAYSCALE,
            }
            tc = compression_map.get(settings["compression"])
            if tc is not None:
                tex.set_editor_property("compression_settings", tc)

        if "lod_group" in settings:
            lod_map = {
                "TEXTUREGROUP_World": unreal.TextureGroup.TEXTUREGROUP_WORLD,
                "TEXTUREGROUP_WorldNormalMap": unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP,
                "TEXTUREGROUP_Character": unreal.TextureGroup.TEXTUREGROUP_CHARACTER,
                "TEXTUREGROUP_CharacterNormalMap": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP,
            }
            lg = lod_map.get(settings["lod_group"])
            if lg is not None:
                tex.set_editor_property("lod_group", lg)

        if "srgb" in settings and settings["srgb"] is not None:
            tex.set_editor_property("srgb", bool(settings["srgb"]))

        if "virtual_texture" in settings:
            tex.set_editor_property("virtual_texture_streaming", bool(settings["virtual_texture"]))

        unreal.EditorAssetLibrary.save_asset(texture_path)
        return True

    def delete_asset(self, asset_path: str) -> bool:
        """删除单个 UE 资产。"""
        if unreal is None:
            return False
        return unreal.EditorAssetLibrary.delete_asset(asset_path)

    def discover_imported_materials(self, isolation_path: str) -> List[str]:
        """列出隔离区中 FBX 导入时自动创建的材质资产。"""
        if unreal is None:
            return []
        all_assets = self.list_assets_in_path(isolation_path)
        materials: List[str] = []
        for asset_path in all_assets:
            clean = asset_path.split(".")[0] if "." in asset_path else asset_path
            obj = unreal.EditorAssetLibrary.load_asset(clean)
            if obj is not None and (
                isinstance(obj, unreal.MaterialInstanceConstant)
                or isinstance(obj, unreal.Material)
            ):
                materials.append(clean)
        return materials

    def read_material_texture_bindings(self, mat_path: str) -> Dict[str, str]:
        """从 MaterialInstanceConstant 读取贴图参数绑定。

        仅返回实际赋值的贴图参数（排除引擎默认值）。

        Returns:
            {参数名: UE 贴图资产路径}，如 {"DiffuseColorMap": "/Game/.../tex"}
        """
        if unreal is None:
            return {}
        mat = unreal.EditorAssetLibrary.load_asset(mat_path)
        if mat is None or not isinstance(mat, unreal.MaterialInstanceConstant):
            return {}

        bindings: Dict[str, str] = {}
        try:
            tex_params = mat.get_editor_property("texture_parameter_values")
            for tp in tex_params:
                info = tp.get_editor_property("parameter_info")
                param_name = str(info.get_editor_property("name"))
                tex = tp.get_editor_property("parameter_value")
                if tex is not None:
                    tex_path = tex.get_path_name()
                    # 去掉 ObjectName 后缀（如 .TextureName）
                    clean = tex_path.split(".")[0] if "." in tex_path else tex_path
                    bindings[param_name] = clean
        except Exception as e:
            logger.warning("Failed to read texture bindings from %s: %s", mat_path, e)
        return bindings

    def get_texture_srgb(self, ue_asset_path: str) -> Optional[bool]:
        """读取 Texture2D 的 sRGB 属性，用于启发式匹配。"""
        if unreal is None:
            return None
        tex = unreal.EditorAssetLibrary.load_asset(ue_asset_path)
        if tex is None or not isinstance(tex, unreal.Texture2D):
            return None
        return tex.get_editor_property("srgb")

    def discover_imported_textures(self, isolation_path: str) -> List[str]:
        """列出隔离区中 FBX 导入时提取的 Texture2D 资产。"""
        if unreal is None:
            return []
        all_assets = self.list_assets_in_path(isolation_path)
        textures = []
        for asset_path in all_assets:
            clean = asset_path.split(".")[0] if "." in asset_path else asset_path
            obj = unreal.EditorAssetLibrary.load_asset(clean)
            if obj is not None and isinstance(obj, unreal.Texture2D):
                textures.append(clean)
        return textures

    def import_texture_file(self, file_path: str, destination_path: str) -> Optional[str]:
        """从磁盘导入一张图片文件为 UE Texture2D 资产。

        Args:
            file_path: 磁盘上的 PNG/TGA 文件绝对路径。
            destination_path: UE Content 目标目录（如 /Game/Assets/Prop/X）。

        Returns:
            导入后的 UE 资产路径，失败返回 None。
        """
        if unreal is None:
            return None

        task = unreal.AssetImportTask()
        task.set_editor_property("filename", file_path)
        task.set_editor_property("destination_path", destination_path)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        imported = task.get_editor_property("imported_object_paths")
        if imported and len(imported) > 0:
            return str(imported[0])
        return None

    def export_texture_to_disk(
        self, ue_asset_path: str, output_dir: str, filename: Optional[str] = None,
    ) -> Optional[str]:
        """将 UE Texture2D 资产导出为 PNG 文件。返回磁盘路径或 None。"""
        if unreal is None:
            return None
        tex = unreal.EditorAssetLibrary.load_asset(ue_asset_path)
        if tex is None:
            return None
        name = filename or ue_asset_path.split("/")[-1]
        if not name.lower().endswith(".png"):
            name += ".png"
        output_path = os.path.join(output_dir, name)
        os.makedirs(output_dir, exist_ok=True)

        task = unreal.AssetExportTask()
        task.set_editor_property("object", tex)
        task.set_editor_property("filename", output_path)
        task.set_editor_property("automated", True)
        task.set_editor_property("prompt", False)
        task.set_editor_property("replace_identical", True)
        ok = unreal.Exporter.run_asset_export_tasks([task])
        if ok and os.path.isfile(output_path):
            return output_path
        return None


# ---------------------------------------------------------------------------
# FBX 自动材质参数名 → 配置逻辑位映射
# ---------------------------------------------------------------------------

FBX_PARAM_TO_SLOT: Dict[str, str] = {
    "DiffuseColorMap": "BaseColor",
    "NormalMap": "Normal",
    "AmbientOcclusionMap": "AmbientOcclusion",
    "SpecularColorMap": "Metallic",
    "ShininessMap": "Roughness",
    "EmissiveColorMap": "Emissive",
    "OpacityMap": "Opacity",
    "OpacityMaskMap": "OpacityMask",
}


def _read_auto_material_slot_mapping(
    ops: UnrealAssetOps,
    isolation_path: str,
    auto_materials: List[str],
) -> Dict[str, str]:
    """从 FBX 自动生成的 MIC 读取贴图→逻辑位映射。

    Returns:
        {slot_name: ue_texture_asset_path}，如 {"BaseColor": "/Game/..."}
    """
    slot_mapping: Dict[str, str] = {}
    for mat_path in auto_materials:
        bindings = ops.read_material_texture_bindings(mat_path)
        for param_name, tex_path in bindings.items():
            slot = FBX_PARAM_TO_SLOT.get(param_name)
            if slot and slot not in slot_mapping:
                slot_mapping[slot] = tex_path
                logger.info(
                    "Auto-material binding: %s (%s) → slot '%s'",
                    param_name, tex_path, slot,
                )
    return slot_mapping


# ---------------------------------------------------------------------------
# 直通判断
# ---------------------------------------------------------------------------

def _is_direct_passthrough(output_def: TextureOutputDef) -> Optional[str]:
    """检查输出定义是否可直接使用单个嵌入贴图（无需 Pillow 处理）。

    条件：所有 RGB 通道来自同一源、同名映射（R→R, G→G, B→B）、
    无 invert/gamma/remap、无 flip_green、bit_depth=8。

    Returns:
        源逻辑位名（如 "BaseColor"），不满足条件则返回 None。
    """
    if output_def.flip_green or output_def.bit_depth != 8:
        return None

    sources = set()
    for ch_name, ch_def in output_def.channels.items():
        if ch_name == "A":
            continue
        if not ch_def.source:
            continue
        if ch_def.invert or ch_def.gamma is not None or ch_def.remap is not None:
            return None
        if ch_name != ch_def.ch:
            return None
        sources.add(ch_def.source)

    return next(iter(sources)) if len(sources) == 1 else None


# ---------------------------------------------------------------------------
# 原生嵌入贴图管线（Native Embedded Texture Pipeline）
# ---------------------------------------------------------------------------

def _find_output_for_slot(
    config: PluginConfig,
    slot_name: str,
) -> Optional[TextureOutputDef]:
    """找到以 slot_name 为唯一来源的 enabled 输出定义。"""
    for output_def in config.texture_output_definitions:
        if not output_def.enabled:
            continue
        sources = {ch.source for ch in output_def.channels.values() if ch.source}
        if sources == {slot_name}:
            return output_def
    return None


def _match_embedded_textures_to_slots(
    ops: UnrealAssetOps,
    ue_textures: List[str],
    config: PluginConfig,
) -> Dict[str, str]:
    """将隔离区中的嵌入贴图匹配到逻辑位。

    策略叠加：
    1. 用现有 input rules 按资产名匹配（glob/regex）
    2. 未匹配的按 sRGB 属性启发式分配（sRGB → BaseColor，!sRGB → Normal）
    3. 唯一剩余贴图 → BaseColor

    Returns:
        {slot_name: ue_asset_path}
    """
    # --- 策略 1：用 matcher 按名称匹配 ---
    path_lookup: Dict[str, str] = {}
    for ue_path in ue_textures:
        asset_name = ue_path.split("/")[-1]
        fake_path = asset_name + ".png"
        path_lookup[fake_path] = ue_path

    match_result = match_textures(list(path_lookup.keys()), config.texture_input_rules)

    slot_mapping: Dict[str, str] = {}
    matched_ue_paths = set()
    for slot, fake_path in match_result.mapping.items():
        ue_path = path_lookup[fake_path]
        slot_mapping[slot] = ue_path
        matched_ue_paths.add(ue_path)

    # --- 策略 2：sRGB 启发式 ---
    unmatched = [p for p in ue_textures if p not in matched_ue_paths]
    if unmatched:
        for ue_path in list(unmatched):
            srgb = ops.get_texture_srgb(ue_path)
            if srgb is True and "BaseColor" not in slot_mapping:
                slot_mapping["BaseColor"] = ue_path
                unmatched.remove(ue_path)
            elif srgb is False and "Normal" not in slot_mapping:
                slot_mapping["Normal"] = ue_path
                unmatched.remove(ue_path)

    # --- 策略 3：单贴图兜底 → BaseColor ---
    if not slot_mapping and len(ue_textures) == 1:
        slot_mapping["BaseColor"] = ue_textures[0]

    return slot_mapping


def _run_native_embedded_pipeline(
    ops: UnrealAssetOps,
    config: PluginConfig,
    category: str,
    current_path: str,
    base_name: str,
    isolation_path: str,
    imported_assets: List[str],
    ue_textures: List[str],
    result: ImportPipelineResult,
) -> ImportPipelineResult:
    """原生嵌入贴图管线：跳过 Pillow，在 UE 资产层面直接操作。

    流程：发现资产 → 读取嵌入贴图 → 删除自动材质 → 匹配+重命名贴图 →
          移动 SM → 创建 MI → 链接贴图 → 绑定 SM → 清理隔离区。
    """
    logger.info(
        "Native embedded pipeline: %d texture(s) in isolation zone", len(ue_textures),
    )

    # 1. 发现自动创建的材质并删除
    auto_materials = ops.discover_imported_materials(isolation_path)
    for mat_path in auto_materials:
        ops.delete_asset(mat_path)
        logger.info("Deleted auto-created material: %s", mat_path)

    # 2. 匹配嵌入贴图到逻辑位
    slot_mapping = _match_embedded_textures_to_slots(ops, ue_textures, config)
    logger.info("Embedded texture slot mapping: %s", slot_mapping)

    if not slot_mapping:
        result.errors.append("嵌入贴图无法匹配到任何逻辑位")
        return result

    # 3. 资产数量检查（找 StaticMesh）
    # imported_object_paths 可能返回 ".ObjectName" 后缀，需清理
    asset_names = [os.path.basename(a).split(".")[0] for a in imported_assets]
    static_mesh_name: Optional[str] = None
    for name in asset_names:
        upper = name.upper()
        if upper.startswith("SM_") or "STATICMESH" in upper:
            static_mesh_name = name
            break
    # 兜底：取隔离区中非 Texture、非 Material 的第一个资产
    if static_mesh_name is None:
        iso_assets = ops.list_assets_in_path(isolation_path)
        for ap in iso_assets:
            clean = ap.split(".")[0] if "." in ap else ap
            if clean not in ue_textures and clean not in auto_materials:
                static_mesh_name = clean.split("/")[-1]
                break
    if static_mesh_name is None:
        result.errors.append("隔离区中未找到 StaticMesh")
        return result

    # 构建简化的 CheckResult 以保持 API 兼容
    result.check_result = CheckResult(
        status=CheckStatus.PASSED,
        static_mesh=static_mesh_name,
        match_result=MatchResult(mapping={s: p for s, p in slot_mapping.items()}),
    )

    # 4. 解析名称
    names = resolve_names(config, base_name, category, current_path)
    result.names = names

    # 5. 解析目标路径（冲突策略）
    result.phase = "standardize"
    final_target = resolve_conflict(
        names.target_path, config.conflict_policy, ops.asset_exists,
    )
    if final_target is None:
        result.errors.append(f"目标路径已存在且策略为 skip: {names.target_path}")
        return result

    # 6-10: UE 资产操作（NFR3: try/except 保护，失败时保留隔离区）
    try:
        # 6. 重命名 + 移动嵌入贴图
        tex_base = names.texture_base_path or final_target
        processed_textures: List[ProcessedTexture] = []
        for slot, ue_tex_path in slot_mapping.items():
            output_def = _find_output_for_slot(config, slot)
            if output_def is None:
                logger.warning("No output definition for slot '%s', skipping texture", slot)
                continue
            new_name = names.texture_names.get(output_def.suffix)
            if new_name is None:
                continue
            new_path = f"{tex_base}/{new_name}"
            ops.rename_asset(ue_tex_path, new_path)
            logger.info("Renamed texture: %s → %s", ue_tex_path, new_path)

            # 应用导入设置
            import_settings_dict = {
                "compression": output_def.import_settings.compression,
                "lod_group": output_def.import_settings.lod_group,
                "srgb": output_def.srgb,
                "virtual_texture": output_def.import_settings.virtual_texture,
            }
            ops.apply_texture_import_settings(new_path, import_settings_dict)

            processed_textures.append(ProcessedTexture(
                output_name=output_def.output_name,
                suffix=output_def.suffix,
                file_path=new_path,
                material_parameter=output_def.material_parameter,
                import_settings=import_settings_dict,
                srgb=output_def.srgb,
            ))

        result.standardize_result = StandardizeResult(textures=processed_textures)

        # 7. 移动 StaticMesh
        sm_src = f"{isolation_path}/{static_mesh_name}"
        sm_dst = names.sm_path or f"{final_target}/{names.static_mesh}"
        ops.rename_asset(sm_src, sm_dst)
        logger.info("Moved StaticMesh: %s → %s", sm_src, sm_dst)

        # 8. 创建 MI 并链接贴图
        mi = None
        if config.default_master_material_path:
            mi_dst = names.mi_path or f"{final_target}/{names.material_instance}"
            mi = ops.create_material_instance(mi_dst, config.default_master_material_path)
            if mi:
                for pt in processed_textures:
                    if pt.material_parameter:
                        ops.set_material_texture_param(mi, pt.material_parameter, pt.file_path)
                        logger.info("Linked %s → MI param '%s'", pt.file_path, pt.material_parameter)

        # 9. 绑定 SM → MI
        if mi:
            ops.set_static_mesh_material(sm_dst, mi_dst)

        # 10. 清理隔离区
        ops.delete_directory(isolation_path)

        result.phase = "done"
    except Exception as e:
        logger.error(
            "Native embedded pipeline failed at standardize phase: %s "
            "— isolation zone preserved: %s", e, isolation_path,
        )
        result.errors.append(f"原生嵌入贴图标准化异常: {e}")

    return result


# ---------------------------------------------------------------------------
# 管道编排
# ---------------------------------------------------------------------------

def run_import_pipeline(
    fbx_path: str,
    config: PluginConfig,
    category: str,
    current_path: str = "/Game",
    ops: Optional[UnrealAssetOps] = None,
) -> ImportPipelineResult:
    """执行完整导入管道：FR2 导入 → FR3 检查 → FR5 标准化。

    Args:
        fbx_path: FBX 文件的绝对磁盘路径。
        config: 加载后的 Profile 配置。
        category: Profile 类别（如 "Prop"）。
        current_path: 当前 Content Browser 路径。
        ops: Unreal 资产操作接口（可 mock）。

    Returns:
        ImportPipelineResult，包含每个阶段的结果。
    """
    if ops is None:
        ops = UnrealAssetOps()

    t_start = time.monotonic()
    result = ImportPipelineResult()
    base_name = extract_base_name(fbx_path)

    # 前置校验：FBX 文件存在性
    if not os.path.isfile(fbx_path):
        result.errors.append(f"FBX 文件不存在: {fbx_path}")
        return result

    # --- 阶段 1：计算隔离区路径并导入 ---
    result.phase = "import"
    isolation_path = compute_isolation_path(
        current_path, base_name, config.default_fallback_import_path,
    )
    result.isolation_path = isolation_path

    try:
        imported_assets = ops.import_fbx(
            fbx_path, isolation_path, import_textures=True,
        )
    except Exception as e:
        result.errors.append(f"FBX 导入失败: {e}")
        return result

    # --- 阶段 2：构建统一贴图清单 ---
    result.phase = "check"

    # 2a: 读取自动材质的贴图通道绑定（在删除前读取）
    auto_materials = ops.discover_imported_materials(isolation_path)
    auto_mat_slots = _read_auto_material_slot_mapping(
        ops, isolation_path, auto_materials,
    )

    # 2b: 删除自动材质
    for mat_path in auto_materials:
        ops.delete_asset(mat_path)
        logger.info("Deleted auto-created material: %s", mat_path)

    # 2c: 发现 UE 隔离区中的嵌入贴图（Texture2D 资产）
    ue_textures = ops.discover_imported_textures(isolation_path)

    # 2d: 发现外部磁盘贴图
    drop_dir = os.path.dirname(fbx_path)
    disk_texture_files = discover_texture_files(
        search_roots=config.texture_input_rules.search_roots,
        extensions=config.texture_input_rules.extensions,
        drop_dir=drop_dir,
    )

    # 2e: 合并两类贴图为统一列表供匹配
    #     外部贴图：使用真实磁盘路径
    #     嵌入贴图：通过自动材质绑定精准映射到逻辑位
    embedded_lookup: Dict[str, str] = {}  # fake_path → ue_asset_path
    ue_texture_set = set(ue_textures)
    disk_basenames = {os.path.basename(p).lower() for p in disk_texture_files}

    # 2e-1: 用自动材质绑定为嵌入贴图生成精准伪文件名
    #       例：slot "BaseColor" + tex "tripo_rgb_xxx" → 伪名使用 slot 名使其必中匹配规则
    mat_bound_textures: set = set()
    for slot, tex_path in auto_mat_slots.items():
        if tex_path not in ue_texture_set:
            continue
        asset_name = tex_path.split("/")[-1]
        fake_path = asset_name + ".png"
        if fake_path.lower() not in disk_basenames:
            embedded_lookup[fake_path] = tex_path
            mat_bound_textures.add(tex_path)

    # 2e-2: 未被材质绑定的嵌入贴图，仍用伪文件名参与 glob 匹配（兜底）
    for ue_path in ue_textures:
        if ue_path in mat_bound_textures:
            continue
        asset_name = ue_path.split("/")[-1]
        fake_path = asset_name + ".png"
        if fake_path.lower() not in disk_basenames:
            embedded_lookup[fake_path] = ue_path

    all_texture_paths = list(disk_texture_files) + list(embedded_lookup.keys())
    logger.info(
        "Unified texture inventory: %d external, %d embedded (%d from auto-material)",
        len(disk_texture_files), len(embedded_lookup), len(mat_bound_textures),
    )

    # --- 阶段 3：检查链 ---
    # imported_object_paths 可能返回 ".ObjectName" 后缀（如 "Mesh.Mesh"），需清理为纯名称
    asset_names = [os.path.basename(a).split(".")[0] for a in imported_assets]

    # 构建排除集合：已识别的贴图和材质名称
    # 用于排除法识别 StaticMesh（应对非标准命名的 FBX，如 Tripo 导出）
    _excluded_basenames: set = set()
    for _p in ue_textures:
        _clean = _p.split(".")[0] if "." in _p else _p
        _excluded_basenames.add(_clean.split("/")[-1])
    for _p in auto_materials:
        _clean = _p.split(".")[0] if "." in _p else _p
        _excluded_basenames.add(_clean.split("/")[-1])

    def _mesh_filter(name: str) -> bool:
        upper = name.upper()
        if upper.startswith("SM_") or "STATICMESH" in upper:
            return True
        # 排除法：非贴图、非材质的资产视为 StaticMesh
        return name not in _excluded_basenames

    check_result = run_check_chain(
        asset_names=asset_names,
        texture_files=all_texture_paths,
        config=config,
        mesh_filter=_mesh_filter,
        material_exists_fn=ops.asset_exists,
    )
    result.check_result = check_result

    # 3.5: 用自动材质绑定覆盖/补充嵌入贴图的匹配结果
    #       内部贴图优先：FBX 自动材质绑定始终覆盖外部匹配
    if auto_mat_slots and check_result.match_result:
        ue_to_fake = {v: k for k, v in embedded_lookup.items()}
        for slot, tex_path in auto_mat_slots.items():
            fake = ue_to_fake.get(tex_path)
            if not fake:
                continue
            old = check_result.match_result.mapping.get(slot)
            if old != fake:
                check_result.match_result.mapping[slot] = fake
                logger.info(
                    "Auto-material binding: slot '%s' = %s (was %s)",
                    slot, fake, old or "(unmapped)",
                )

    if not check_result.passed:
        # 检查失败 → 停在隔离区，保存上下文供分诊 UI 恢复
        result.triage_context = TriageContext(
            config=config,
            category=category,
            current_path=current_path,
            base_name=base_name,
            embedded_lookup=dict(embedded_lookup),
            all_texture_paths=list(all_texture_paths),
        )
        return result

    # --- 阶段 4：解析名称 ---
    names = resolve_names(config, base_name, category, current_path)
    result.names = names

    # --- 阶段 5：标准化（嵌入贴图直通 + Pillow 后处理）---
    # NFR3: try/except 保护，失败时保留隔离区 + 清晰日志
    result.phase = "standardize"
    try:
        mapping = check_result.match_result.mapping if check_result.match_result else {}

        # 5.1 识别可直接使用嵌入贴图的输出（passthrough：同源同通道、无变换）
        direct_suffixes: Dict[str, tuple] = {}  # suffix → (output_def, ue_tex_path)
        for output_def in config.texture_output_definitions:
            if not output_def.enabled:
                continue
            source_slot = _is_direct_passthrough(output_def)
            if source_slot is None or source_slot not in mapping:
                continue
            matched_path = mapping[source_slot]
            if matched_path not in embedded_lookup:
                continue
            direct_suffixes[output_def.suffix] = (output_def, embedded_lookup[matched_path])

        if direct_suffixes:
            logger.info(
                "Direct embedded passthrough outputs: %s",
                ", ".join(f"{s} ({od.output_name})" for s, (od, _) in direct_suffixes.items()),
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 5.2 构建 Pillow 源映射
            #     外部贴图：直接使用磁盘文件
            #     嵌入贴图：导出到临时目录（供 Pillow 使用）
            pillow_mapping: Dict[str, str] = {}
            for slot, matched_path in mapping.items():
                if matched_path in embedded_lookup:
                    ue_path = embedded_lookup[matched_path]
                    disk_path = ops.export_texture_to_disk(ue_path, tmp_dir)
                    if disk_path:
                        pillow_mapping[slot] = disk_path
                        logger.info(
                            "Exported embedded texture for slot '%s': %s → %s",
                            slot, ue_path, disk_path,
                        )
                    else:
                        logger.warning(
                            "Failed to export embedded texture for slot '%s': %s",
                            slot, ue_path,
                        )
                else:
                    pillow_mapping[slot] = matched_path

            # 5.3 Pillow 处理（跳过已直接处理的输出）
            if direct_suffixes:
                pillow_config = copy.deepcopy(config)
                for od in pillow_config.texture_output_definitions:
                    if od.suffix in direct_suffixes:
                        od.enabled = False
            else:
                pillow_config = config

            std_result = process_textures(
                pillow_config, pillow_mapping, tmp_dir, base_name, category,
            )

            if not std_result.success:
                result.errors.extend(std_result.errors)
                return result

            # 5.4 解析目标路径（冲突策略）
            target_path = names.target_path
            final_target = resolve_conflict(
                target_path, config.conflict_policy, ops.asset_exists,
            )
            if final_target is None:
                result.errors.append(f"目标路径已存在且策略为 skip: {target_path}")
                return result

            # 子目录路径
            tex_base = names.texture_base_path or final_target
            sm_dst_path = names.sm_path or f"{final_target}/{names.static_mesh}"
            mi_dst_path = names.mi_path or f"{final_target}/{names.material_instance}"

            # 移动 StaticMesh
            if check_result.static_mesh:
                sm_src = f"{isolation_path}/{check_result.static_mesh}"
                ops.rename_asset(sm_src, sm_dst_path)

            # 5.5 处理直接嵌入贴图（重命名 + 移动 + 应用导入设置）
            all_processed: List[ProcessedTexture] = []
            for suffix, (output_def, ue_tex_path) in direct_suffixes.items():
                tex_name = names.texture_names.get(suffix)
                if not tex_name:
                    continue
                new_path = f"{tex_base}/{tex_name}"
                ops.rename_asset(ue_tex_path, new_path)
                imp = output_def.import_settings
                settings = {
                    "compression": imp.compression,
                    "lod_group": imp.lod_group,
                    "srgb": output_def.srgb,
                    "virtual_texture": imp.virtual_texture,
                }
                ops.apply_texture_import_settings(new_path, settings)
                all_processed.append(ProcessedTexture(
                    output_name=output_def.output_name,
                    suffix=suffix,
                    file_path=new_path,
                    material_parameter=output_def.material_parameter,
                    import_settings=settings,
                    srgb=output_def.srgb,
                ))
                logger.info("Direct embedded texture: %s → %s", ue_tex_path, new_path)

            # 5.6 导入 Pillow 标准化贴图为 UE 资产
            for proc_tex in std_result.textures:
                imported_path = ops.import_texture_file(proc_tex.file_path, tex_base)
                if imported_path:
                    logger.info("Imported texture: %s → %s", proc_tex.file_path, imported_path)
                else:
                    logger.warning("Failed to import texture: %s", proc_tex.file_path)

            all_processed.extend(std_result.textures)
            result.standardize_result = StandardizeResult(textures=all_processed)

            # 5.7 MIC 创建
            mi = None
            if config.default_master_material_path:
                mi = ops.create_material_instance(mi_dst_path, config.default_master_material_path)

                for proc_tex in all_processed:
                    tex_ue_name = os.path.splitext(os.path.basename(proc_tex.file_path))[0]
                    tex_ue_path = f"{tex_base}/{tex_ue_name}"
                    if mi and proc_tex.material_parameter:
                        ops.set_material_texture_param(mi, proc_tex.material_parameter, tex_ue_path)
                    # Pillow 输出需应用导入设置；直接输出已在 5.5 中应用
                    if proc_tex.suffix not in direct_suffixes:
                        ops.apply_texture_import_settings(tex_ue_path, proc_tex.import_settings)

            # 5.8 绑定 SM → MI
            if mi and check_result.static_mesh:
                ops.set_static_mesh_material(sm_dst_path, mi_dst_path)

            # 5.9 清理隔离区
            ops.delete_directory(isolation_path)

            result.phase = "done"
    except Exception as e:
        logger.error(
            "Import pipeline failed at standardize phase: %s "
            "— isolation zone preserved: %s", e, isolation_path,
        )
        result.errors.append(f"标准化阶段异常: {e}")

    # NFR1: 性能预算检查
    elapsed = time.monotonic() - t_start
    if result.success:
        if elapsed > _PERF_BUDGET_SECONDS:
            logger.warning(
                "Pipeline exceeded performance budget: %.2fs > %.1fs",
                elapsed, _PERF_BUDGET_SECONDS,
            )
        else:
            logger.info("Pipeline completed in %.2fs (budget: %.1fs)", elapsed, _PERF_BUDGET_SECONDS)
    else:
        logger.info("Pipeline stopped at phase '%s' after %.2fs", result.phase, elapsed)

    return result


# ---------------------------------------------------------------------------
# FR4 → FR5 恢复执行
# ---------------------------------------------------------------------------

def resume_after_triage(
    pipeline_result: ImportPipelineResult,
    corrected_mapping: Dict[str, str],
    corrected_base_name: Optional[str] = None,
    ops: Optional[UnrealAssetOps] = None,
) -> ImportPipelineResult:
    """FR4 分诊完成后，用修正后的映射继续执行 FR5 标准化。

    Args:
        pipeline_result: run_import_pipeline 返回的（失败）结果。
        corrected_mapping: 用户在分诊 UI 中修正后的 {slot: file_path} 映射。
        corrected_base_name: 用户修正后的资产基础名，None 则沿用原值。
        ops: Unreal 资产操作接口。

    Returns:
        更新后的 ImportPipelineResult。
    """
    if ops is None:
        ops = UnrealAssetOps()

    t_start = time.monotonic()

    tc = pipeline_result.triage_context
    if tc is None or tc.config is None:
        pipeline_result.errors.append("缺少分诊上下文，无法恢复管线")
        return pipeline_result

    config = tc.config
    category = tc.category
    current_path = tc.current_path
    base_name = corrected_base_name or tc.base_name
    isolation_path = pipeline_result.isolation_path
    embedded_lookup = tc.embedded_lookup

    check_result = pipeline_result.check_result
    if check_result is None:
        pipeline_result.errors.append("缺少检查结果")
        return pipeline_result

    # 用修正后的映射覆盖原始映射
    if check_result.match_result is None:
        check_result.match_result = MatchResult()
    check_result.match_result.mapping = dict(corrected_mapping)

    # --- 阶段 4：解析名称 ---
    names = resolve_names(config, base_name, category, current_path)
    pipeline_result.names = names

    # --- 阶段 5：标准化 ---
    # NFR3: try/except 保护，失败时保留隔离区 + 清晰日志
    pipeline_result.phase = "standardize"
    try:
        mapping = check_result.match_result.mapping

        # 5.1 识别直通嵌入贴图
        direct_suffixes: Dict[str, tuple] = {}
        for output_def in config.texture_output_definitions:
            if not output_def.enabled:
                continue
            source_slot = _is_direct_passthrough(output_def)
            if source_slot is None or source_slot not in mapping:
                continue
            matched_path = mapping[source_slot]
            if matched_path not in embedded_lookup:
                continue
            direct_suffixes[output_def.suffix] = (output_def, embedded_lookup[matched_path])

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 5.2 Pillow 源映射
            pillow_mapping: Dict[str, str] = {}
            for slot, matched_path in mapping.items():
                if matched_path in embedded_lookup:
                    ue_path = embedded_lookup[matched_path]
                    disk_path = ops.export_texture_to_disk(ue_path, tmp_dir)
                    if disk_path:
                        pillow_mapping[slot] = disk_path
                    else:
                        logger.warning(
                            "Failed to export embedded texture for slot '%s': %s",
                            slot, ue_path,
                        )
                else:
                    pillow_mapping[slot] = matched_path

            # 5.3 Pillow 处理
            if direct_suffixes:
                pillow_config = copy.deepcopy(config)
                for od in pillow_config.texture_output_definitions:
                    if od.suffix in direct_suffixes:
                        od.enabled = False
            else:
                pillow_config = config

            std_result = process_textures(
                pillow_config, pillow_mapping, tmp_dir, base_name, category,
            )

            if not std_result.success:
                pipeline_result.errors.extend(std_result.errors)
                return pipeline_result

            # 5.4 目标路径
            target_path = names.target_path
            final_target = resolve_conflict(
                target_path, config.conflict_policy, ops.asset_exists,
            )
            if final_target is None:
                pipeline_result.errors.append(f"目标路径已存在且策略为 skip: {target_path}")
                return pipeline_result

            # 子目录路径
            tex_base = names.texture_base_path or final_target
            sm_dst_path = names.sm_path or f"{final_target}/{names.static_mesh}"
            mi_dst_path = names.mi_path or f"{final_target}/{names.material_instance}"

            # 移动 StaticMesh
            if check_result.static_mesh:
                sm_src = f"{isolation_path}/{check_result.static_mesh}"
                ops.rename_asset(sm_src, sm_dst_path)

            # 5.5 直接嵌入贴图
            all_processed: List[ProcessedTexture] = []
            for suffix, (output_def, ue_tex_path) in direct_suffixes.items():
                tex_name = names.texture_names.get(suffix)
                if not tex_name:
                    continue
                new_path = f"{tex_base}/{tex_name}"
                ops.rename_asset(ue_tex_path, new_path)
                imp = output_def.import_settings
                settings = {
                    "compression": imp.compression,
                    "lod_group": imp.lod_group,
                    "srgb": output_def.srgb,
                    "virtual_texture": imp.virtual_texture,
                }
                ops.apply_texture_import_settings(new_path, settings)
                all_processed.append(ProcessedTexture(
                    output_name=output_def.output_name,
                    suffix=suffix,
                    file_path=new_path,
                    material_parameter=output_def.material_parameter,
                    import_settings=settings,
                    srgb=output_def.srgb,
                ))

            # 5.6 导入 Pillow 贴图
            for proc_tex in std_result.textures:
                ops.import_texture_file(proc_tex.file_path, tex_base)

            all_processed.extend(std_result.textures)
            pipeline_result.standardize_result = StandardizeResult(textures=all_processed)

            # 5.7 MIC 创建
            mi = None
            if config.default_master_material_path:
                mi = ops.create_material_instance(mi_dst_path, config.default_master_material_path)

                for proc_tex in all_processed:
                    tex_ue_name = os.path.splitext(os.path.basename(proc_tex.file_path))[0]
                    tex_ue_path = f"{tex_base}/{tex_ue_name}"
                    if mi and proc_tex.material_parameter:
                        ops.set_material_texture_param(mi, proc_tex.material_parameter, tex_ue_path)
                    if proc_tex.suffix not in direct_suffixes:
                        ops.apply_texture_import_settings(tex_ue_path, proc_tex.import_settings)

            # 5.8 绑定 SM → MI
            if mi and check_result.static_mesh:
                ops.set_static_mesh_material(sm_dst_path, mi_dst_path)

            # 5.9 清理隔离区
            ops.delete_directory(isolation_path)

        pipeline_result.phase = "done"
    except Exception as e:
        logger.error(
            "Resume-after-triage failed at standardize phase: %s "
            "— isolation zone preserved: %s", e, isolation_path,
        )
        pipeline_result.errors.append(f"分诊后标准化异常: {e}")

    # NFR1: 性能预算检查
    elapsed = time.monotonic() - t_start
    if pipeline_result.success:
        if elapsed > _PERF_BUDGET_SECONDS:
            logger.warning(
                "Resume-after-triage exceeded performance budget: %.2fs > %.1fs",
                elapsed, _PERF_BUDGET_SECONDS,
            )
        else:
            logger.info("Resume-after-triage completed in %.2fs (budget: %.1fs)", elapsed, _PERF_BUDGET_SECONDS)
    else:
        logger.info("Resume-after-triage stopped at phase '%s' after %.2fs", pipeline_result.phase, elapsed)

    return pipeline_result


# ---------------------------------------------------------------------------
# M4: 批处理
# ---------------------------------------------------------------------------

@dataclass
class BatchItemResult:
    """单个 FBX 在批处理中的结果。"""
    fbx_path: str = ""
    pipeline_result: Optional[ImportPipelineResult] = None
    needs_triage: bool = False


@dataclass
class BatchImportResult:
    """批量导入的汇总结果。"""
    items: List[BatchItemResult] = field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    needs_triage: int = 0
    elapsed: float = 0.0

    @property
    def summary(self) -> str:
        parts = [f"批处理完成: {self.total} 个文件"]
        if self.succeeded:
            parts.append(f"{self.succeeded} 成功")
        if self.needs_triage:
            parts.append(f"{self.needs_triage} 待分诊")
        if self.failed:
            parts.append(f"{self.failed} 失败")
        parts.append(f"耗时 {self.elapsed:.1f}s")
        return ", ".join(parts)


def run_batch_import(
    fbx_paths: List[str],
    config: PluginConfig,
    category: str,
    current_path: str = "/Game",
    ops: Optional[UnrealAssetOps] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> BatchImportResult:
    """批量执行导入管道。

    逐个处理 FBX 文件，检查失败的文件标记为 needs_triage，
    不阻塞后续文件的处理。

    Args:
        fbx_paths: FBX 文件路径列表。
        config: Profile 配置。
        category: Profile 类别。
        current_path: Content Browser 路径。
        ops: UE 资产操作接口。
        on_progress: 进度回调 (current_index, total, fbx_filename)。

    Returns:
        BatchImportResult 汇总。
    """
    if ops is None:
        ops = UnrealAssetOps()

    t_start = time.monotonic()
    batch = BatchImportResult(total=len(fbx_paths))

    for idx, fbx_path in enumerate(fbx_paths):
        filename = os.path.basename(fbx_path)
        logger.info("Batch [%d/%d]: %s", idx + 1, batch.total, filename)

        if on_progress:
            try:
                on_progress(idx + 1, batch.total, filename)
            except Exception:
                pass

        item = BatchItemResult(fbx_path=fbx_path)
        try:
            result = run_import_pipeline(
                fbx_path=fbx_path,
                config=config,
                category=category,
                current_path=current_path,
                ops=ops,
            )
            item.pipeline_result = result

            if result.success:
                batch.succeeded += 1
            elif result.check_result and not result.check_result.passed:
                item.needs_triage = True
                batch.needs_triage += 1
            else:
                batch.failed += 1
        except Exception as e:
            logger.error("Batch [%d/%d] unexpected error: %s", idx + 1, batch.total, e)
            item.pipeline_result = ImportPipelineResult(
                errors=[f"批处理异常: {e}"],
            )
            batch.failed += 1

        batch.items.append(item)

    batch.elapsed = time.monotonic() - t_start
    logger.info(batch.summary)
    return batch
