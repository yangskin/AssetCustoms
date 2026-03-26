import json
from typing import Any, Dict, List, Optional, Union
from .schema import (
    ChannelDef,
    InputConfig,
    MaterialOutputConfig,
    MeshImportConfig,
    NamingConfig,
    OutputConfig,
    PluginConfig,
    ProcessingConfig,
    SubdirectoriesConfig,
    TextureImportDefaults,
    TextureInputConfig,
    TextureInputRule,
    TextureProcessingDef,
)
from .jsonc import load_jsonc_file, loads_jsonc


# ---------------------------------------------------------------------------
# 低层解析辅助函数
# ---------------------------------------------------------------------------

def _parse_max_resolution(raw: Any) -> Optional[int]:
    """兼容解析 max_resolution：新格式 int / 旧格式 {"width": N, "height": N}。"""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, dict):
        return max(raw.get("width", 0), raw.get("height", 0)) or None
    return None


def _parse_channel_def(data: Dict[str, Any]) -> ChannelDef:
    return ChannelDef(
        source=data.get("from", ""),
        ch=data.get("ch", "R"),
        constant=data.get("constant"),
        invert=bool(data.get("invert", False)),
        gamma=data.get("gamma"),
        remap=data.get("remap"),
    )


# ---------------------------------------------------------------------------
# Input 段
# ---------------------------------------------------------------------------

def _parse_texture_input(data: Dict[str, Any]) -> TextureInputConfig:
    rules_raw = data.get("rules", {}) or {}
    rules: Dict[str, TextureInputRule] = {}
    for name, rd in rules_raw.items():
        rules[name] = TextureInputRule(
            priority=int(rd.get("priority", 10)),
            patterns=list(rd.get("patterns", [])),
        )
    return TextureInputConfig(
        match_mode=data.get("match_mode", "glob"),
        ignore_case=bool(data.get("ignore_case", True)),
        extensions=list(data.get("extensions", TextureInputConfig().extensions)),
        search_roots=list(data.get("search_roots", TextureInputConfig().search_roots)),
        rules=rules,
    )


def _parse_input(data: Dict[str, Any]) -> InputConfig:
    cfg = InputConfig()
    tex = data.get("texture")
    if isinstance(tex, dict):
        cfg.texture = _parse_texture_input(tex)
    return cfg


# ---------------------------------------------------------------------------
# Processing 段
# ---------------------------------------------------------------------------

def _parse_texture_processing_def(data: Dict[str, Any]) -> TextureProcessingDef:
    channels_raw = data.get("channels", {}) or {}
    channels = {k: _parse_channel_def(v) for k, v in channels_raw.items()}
    return TextureProcessingDef(
        enabled=bool(data.get("enabled", True)),
        name=data.get("name", ""),
        suffix=data.get("suffix", ""),
        category=data.get("category", "PBR"),
        channels=channels,
        flip_green=bool(data.get("flip_green", False)),
        normal_space=data.get("normal_space"),
        allow_missing=bool(data.get("allow_missing", False)),
        format=data.get("format", "PNG"),
        bit_depth=int(data.get("bit_depth", 8)),
        srgb=bool(data.get("srgb", True)),
        mips=bool(data.get("mips", True)),
        resize=data.get("resize"),
        alpha_premultiplied=bool(data.get("alpha_premultiplied", False)),
        max_resolution=_parse_max_resolution(data.get("max_resolution")),
    )


def _parse_mesh_import(data: Dict[str, Any]) -> MeshImportConfig:
    cfg = MeshImportConfig()
    _SIMPLE_FLOAT = {"import_uniform_scale"}
    _SIMPLE_BOOL = {
        "import_as_skeletal", "compute_weighted_normals", "import_animations",
        "auto_generate_collision", "combine_meshes", "remove_degenerates",
        "build_nanite", "build_reversed_index_buffer", "generate_lightmap_u_vs",
        "convert_scene", "convert_scene_unit", "force_front_x_axis",
        "import_mesh_lods", "import_materials", "import_textures",
        "reorder_material_to_fbx_order",
        # SkeletalMesh 专有
        "create_physics_asset", "import_morph_targets",
        "import_meshes_in_bone_hierarchy", "update_skeleton_reference_pose",
        "use_t0_as_ref_pose", "preserve_smoothing_groups",
    }
    _SIMPLE_STR = {
        "normal_import_method", "normal_generation_method",
        "vertex_color_import_option", "static_mesh_lod_group",
        # SkeletalMesh 专有
        "skeleton_path", "import_content_type",
    }
    for k in _SIMPLE_FLOAT:
        if k in data:
            setattr(cfg, k, float(data[k]))
    for k in _SIMPLE_BOOL:
        if k in data:
            setattr(cfg, k, bool(data[k]))
    for k in _SIMPLE_STR:
        if k in data:
            setattr(cfg, k, str(data[k]))
    if "vertex_override_color" in data:
        v = data["vertex_override_color"]
        if isinstance(v, list) and len(v) >= 3:
            cfg.vertex_override_color = [int(c) for c in v[:4]] if len(v) >= 4 else [int(c) for c in v[:3]] + [255]
    if "import_rotation" in data:
        v = data["import_rotation"]
        if isinstance(v, list) and len(v) >= 3:
            cfg.import_rotation = [float(x) for x in v[:3]]
    if "import_translation" in data:
        v = data["import_translation"]
        if isinstance(v, list) and len(v) >= 3:
            cfg.import_translation = [float(x) for x in v[:3]]
    return cfg


def _parse_processing(data: Dict[str, Any]) -> ProcessingConfig:
    cfg = ProcessingConfig()
    if "conflict_policy" in data:
        cfg.conflict_policy = str(data["conflict_policy"])
    mi = data.get("mesh_import")
    if isinstance(mi, dict):
        cfg.mesh_import = _parse_mesh_import(mi)
    td = data.get("texture_definitions")
    if isinstance(td, list):
        cfg.texture_definitions = [_parse_texture_processing_def(d) for d in td if isinstance(d, dict)]
    return cfg


# ---------------------------------------------------------------------------
# Output 段
# ---------------------------------------------------------------------------

def _parse_texture_import_defaults(data: Dict[str, Any]) -> TextureImportDefaults:
    return TextureImportDefaults(
        compression=data.get("compression", "TC_Default"),
        lod_group=data.get("lod_group", "TEXTUREGROUP_World"),
        srgb=data.get("srgb"),
        virtual_texture=bool(data.get("virtual_texture", False)),
        address_x=data.get("address_x", "Wrap"),
        address_y=data.get("address_y", "Wrap"),
        mip_gen=data.get("mip_gen", "FromTextureGroup"),
        max_resolution=_parse_max_resolution(data.get("max_resolution")),
    )


def _parse_output(data: Dict[str, Any]) -> OutputConfig:
    cfg = OutputConfig()
    if "target_path_template" in data:
        cfg.target_path_template = str(data["target_path_template"])
    if "fallback_path" in data:
        cfg.fallback_path = str(data["fallback_path"])

    # 子目录
    sd = data.get("subdirectories")
    if isinstance(sd, dict):
        cfg.subdirectories = SubdirectoriesConfig(
            static_mesh=str(sd.get("static_mesh", "")),
            material_instance=str(sd.get("material_instance", "")),
            texture=str(sd.get("texture", "")),
        )

    # 命名
    nm = data.get("naming")
    if isinstance(nm, dict):
        cfg.naming = NamingConfig(
            static_mesh=nm.get("static_mesh", "SM_{Name}"),
            material_instance=nm.get("material_instance", "MI_{Name}"),
            texture=nm.get("texture", "T_{Name}_{Suffix}"),
        )

    # 材质交付
    mat = data.get("material")
    if isinstance(mat, dict):
        cfg.material = MaterialOutputConfig(
            master_material_path=str(mat.get("master_material_path", "")),
            parameter_bindings=dict(mat.get("parameter_bindings", {})),
        )

    # 贴图导入默认值
    tid = data.get("texture_import_defaults")
    if isinstance(tid, dict):
        cfg.texture_import_defaults = _parse_texture_import_defaults(tid)

    # 贴图导入覆盖（suffix → partial dict）
    tio = data.get("texture_import_overrides")
    if isinstance(tio, dict):
        cfg.texture_import_overrides = {str(k): dict(v) for k, v in tio.items() if isinstance(v, dict)}

    return cfg


# ---------------------------------------------------------------------------
# 顶层加载
# ---------------------------------------------------------------------------

def load_config_from_dict(data: Dict[str, Any], base: Optional[PluginConfig] = None) -> PluginConfig:
    cfg = base or PluginConfig()

    if "config_version" in data:
        cfg.config_version = str(data["config_version"])

    # Input 段
    inp = data.get("input")
    if isinstance(inp, dict):
        cfg.input = _parse_input(inp)

    # Processing 段
    proc = data.get("processing")
    if isinstance(proc, dict):
        cfg.processing = _parse_processing(proc)

    # Output 段
    out = data.get("output")
    if isinstance(out, dict):
        cfg.output = _parse_output(out)

    return cfg


def load_config(src: Union[str, Dict[str, Any]], base: Optional[PluginConfig] = None) -> PluginConfig:
    """
    从文件路径（.jsonc/.json）或字典载入配置，并合并到默认配置。
    优先尝试 JSONC（json5 或注释剥离），失败再退回标准 JSON。
    """
    if isinstance(src, dict):
        return load_config_from_dict(src, base)

    try:
        data = load_jsonc_file(src)
    except Exception:
        with open(src, "r", encoding="utf-8") as f:
            text = f.read()
        try:
            data = json.loads(text)
        except Exception:
            data = loads_jsonc(text)
    return load_config_from_dict(data, base)
