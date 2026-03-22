import json
from typing import Any, Dict, List, Optional, Union
from core.textures.layer_merge import BlendMode
from .schema import (
    AssetNamingTemplate,
    ChannelDef,
    ImportSettings,
    PluginConfig,
    TextureInputRule,
    TextureInputRules,
    TextureMergeDefaults,
    TextureOutputDef,
)
from .jsonc import load_jsonc_file, loads_jsonc


def _merge_dict(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d)
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)  # type: ignore[index]
        else:
            out[k] = v
    return out


def _parse_naming_template(data: Dict[str, Any]) -> AssetNamingTemplate:
    return AssetNamingTemplate(
        static_mesh=data.get("static_mesh", "SM_{Name}"),
        material_instance=data.get("material_instance", "MI_{Name}"),
        texture=data.get("texture", "T_{Name}_{Suffix}"),
    )


def _parse_input_rules(data: Dict[str, Any]) -> TextureInputRules:
    rules_raw = data.get("rules", {}) or {}
    rules: Dict[str, TextureInputRule] = {}
    for name, rd in rules_raw.items():
        rules[name] = TextureInputRule(
            priority=int(rd.get("priority", 10)),
            patterns=list(rd.get("patterns", [])),
        )
    return TextureInputRules(
        match_mode=data.get("match_mode", "glob"),
        ignore_case=bool(data.get("ignore_case", True)),
        extensions=list(data.get("extensions", TextureInputRules().extensions)),
        search_roots=list(data.get("search_roots", TextureInputRules().search_roots)),
        rules=rules,
    )


def _parse_channel_def(data: Dict[str, Any]) -> ChannelDef:
    return ChannelDef(
        source=data.get("from", ""),
        ch=data.get("ch", "R"),
        constant=data.get("constant"),
        invert=bool(data.get("invert", False)),
        gamma=data.get("gamma"),
        remap=data.get("remap"),
    )


def _parse_import_settings(data: Dict[str, Any]) -> ImportSettings:
    return ImportSettings(
        compression=data.get("compression", "TC_Default"),
        lod_group=data.get("lod_group", "TEXTUREGROUP_World"),
        srgb=data.get("srgb"),
        virtual_texture=bool(data.get("virtual_texture", False)),
        address_x=data.get("address_x", "Wrap"),
        address_y=data.get("address_y", "Wrap"),
        mip_gen=data.get("mip_gen", "FromTextureGroup"),
    )


def _parse_output_def(data: Dict[str, Any]) -> TextureOutputDef:
    channels_raw = data.get("channels", {}) or {}
    channels = {k: _parse_channel_def(v) for k, v in channels_raw.items()}
    imp = data.get("import_settings")
    return TextureOutputDef(
        enabled=bool(data.get("enabled", True)),
        output_name=data.get("output_name", ""),
        suffix=data.get("suffix", ""),
        category=data.get("category", "PBR"),
        srgb=bool(data.get("srgb", True)),
        file_format=data.get("file_format", "PNG"),
        bit_depth=int(data.get("bit_depth", 8)),
        mips=bool(data.get("mips", True)),
        resize=data.get("resize"),
        alpha_premultiplied=bool(data.get("alpha_premultiplied", False)),
        material_parameter=data.get("material_parameter", ""),
        allow_missing=bool(data.get("allow_missing", False)),
        normal_space=data.get("normal_space"),
        flip_green=bool(data.get("flip_green", False)),
        channels=channels,
        import_settings=_parse_import_settings(imp) if imp else ImportSettings(),
    )


def load_config_from_dict(data: Dict[str, Any], base: Optional[PluginConfig] = None) -> PluginConfig:
    cfg = base or PluginConfig()

    # --- V1.1 顶层字段 ---
    if "config_version" in data:
        cfg.config_version = str(data["config_version"])
    if "default_master_material_path" in data:
        cfg.default_master_material_path = str(data["default_master_material_path"])
    if "default_fallback_import_path" in data:
        cfg.default_fallback_import_path = str(data["default_fallback_import_path"])
    if "target_path_template" in data:
        cfg.target_path_template = str(data["target_path_template"])
    if "conflict_policy" in data:
        cfg.conflict_policy = str(data["conflict_policy"])

    # --- 资产命名模板 ---
    ant = data.get("asset_naming_template")
    if isinstance(ant, dict):
        cfg.asset_naming_template = _parse_naming_template(ant)

    # --- 贴图输入识别规则 ---
    tir = data.get("texture_input_rules")
    if isinstance(tir, dict):
        cfg.texture_input_rules = _parse_input_rules(tir)

    # --- 输出贴图定义 ---
    tod = data.get("texture_output_definitions")
    if isinstance(tod, list):
        cfg.texture_output_definitions = [_parse_output_def(d) for d in tod if isinstance(d, dict)]

    # --- 旧版兼容：texture_merge / allowed_modes ---
    tm = data.get("texture_merge", {}) or {}
    if tm:
        mode = tm.get("mode", getattr(cfg.texture_merge.mode, "value", cfg.texture_merge.mode))
        opacity = tm.get("opacity", cfg.texture_merge.opacity)
        cfg.texture_merge = TextureMergeDefaults(
            mode=BlendMode(mode) if isinstance(mode, str) else mode,
            opacity=float(opacity),
        )
    allowed = data.get("allowed_modes")
    if allowed:
        cfg.allowed_modes = [BlendMode(m) if isinstance(m, str) else m for m in allowed]
    return cfg


def load_config(src: Union[str, Dict[str, Any]], base: Optional[PluginConfig] = None) -> PluginConfig:
    """
    从文件路径（.jsonc/.json）或字典载入配置，并合并到默认配置。
    - 优先尝试 JSONC（json5 或注释剥离），失败再退回标准 JSON。
    """
    if isinstance(src, dict):
        return load_config_from_dict(src, base)

    try:
        # 优先尝试 JSONC（对 .jsonc 与多数 .json 也适用）
        data = load_jsonc_file(src)
    except Exception:
        with open(src, "r", encoding="utf-8") as f:
            text = f.read()
        try:
            data = json.loads(text)
        except Exception:
            # 即便扩展名是 .json，也尝试 JSONC 解析一次
            data = loads_jsonc(text)
    return load_config_from_dict(data, base)
