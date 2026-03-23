"""测试 Schema v1.1 全量字段解析（从 Prop.jsonc 级别的完整配置加载）。"""
import os
import sys
import tempfile
import pytest

THIS_DIR = os.path.dirname(__file__)
PYTHON_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from core.config.loader import load_config, load_config_from_dict
from core.config.schema import (
    PluginConfig,
    AssetNamingTemplate,
    ChannelDef,
    ImportSettings,
    TextureInputRule,
    TextureInputRules,
    TextureOutputDef,
)


# ---------------------------------------------------------------------------
# 最小 V1.1 字典（覆盖所有顶层 + 一个完整 output_def）
# ---------------------------------------------------------------------------
MINIMAL_V11 = {
    "config_version": "1.1",
    "default_master_material_path": "/Game/M/MM_PBR.MM_PBR",
    "default_fallback_import_path": "/Game/Drop",
    "target_path_template": "/Game/{Category}/{Name}",
    "conflict_policy": "skip",
    "asset_naming_template": {
        "static_mesh": "SM_{Name}",
        "material_instance": "MI_{Name}",
        "texture": "T_{Name}_{Suffix}",
    },
    "texture_input_rules": {
        "match_mode": "regex",
        "ignore_case": False,
        "extensions": [".png", ".tga"],
        "search_roots": ["{DropDir}"],
        "rules": {
            "BaseColor": {"priority": 10, "patterns": [".*_bc.*"]},
            "Normal": {"priority": 9, "patterns": [".*_n$", ".*_normal.*"]},
        },
    },
    "texture_output_definitions": [
        {
            "enabled": True,
            "output_name": "Packed_MRO",
            "suffix": "MRO",
            "category": "PBR",
            "srgb": False,
            "file_format": "PNG",
            "bit_depth": 8,
            "mips": True,
            "allow_missing": True,
            "material_parameter": "Packed_Texture",
            "channels": {
                "R": {"from": "Metallic", "ch": "R", "constant": 0.0},
                "G": {"from": "Roughness", "ch": "R", "constant": 0.5, "invert": True},
                "B": {"from": "AmbientOcclusion", "ch": "R", "constant": 1.0},
                "A": {"constant": 1.0},
            },
            "import_settings": {
                "compression": "TC_Masks",
                "lod_group": "TEXTUREGROUP_World",
                "virtual_texture": False,
            },
        }
    ],
}


def test_load_v11_toplevel():
    cfg = load_config_from_dict(MINIMAL_V11)
    assert cfg.config_version == "1.1"
    assert cfg.default_master_material_path == "/Game/M/MM_PBR.MM_PBR"
    assert cfg.default_fallback_import_path == "/Game/Drop"
    assert cfg.target_path_template == "/Game/{Category}/{Name}"
    assert cfg.conflict_policy == "skip"


def test_load_v11_naming_template():
    cfg = load_config_from_dict(MINIMAL_V11)
    assert isinstance(cfg.asset_naming_template, AssetNamingTemplate)
    assert cfg.asset_naming_template.static_mesh == "SM_{Name}"
    assert cfg.asset_naming_template.texture == "T_{Name}_{Suffix}"


def test_load_v11_input_rules():
    cfg = load_config_from_dict(MINIMAL_V11)
    tir = cfg.texture_input_rules
    assert isinstance(tir, TextureInputRules)
    assert tir.match_mode == "regex"
    assert tir.ignore_case is False
    assert tir.extensions == [".png", ".tga"]
    assert "BaseColor" in tir.rules
    assert tir.rules["BaseColor"].priority == 10
    assert tir.rules["BaseColor"].patterns == [".*_bc.*"]
    assert tir.rules["Normal"].priority == 9


def test_load_v11_output_definitions():
    cfg = load_config_from_dict(MINIMAL_V11)
    assert len(cfg.texture_output_definitions) == 1
    od = cfg.texture_output_definitions[0]
    assert isinstance(od, TextureOutputDef)
    assert od.output_name == "Packed_MRO"
    assert od.suffix == "MRO"
    assert od.srgb is False
    assert od.allow_missing is True
    assert od.material_parameter == "Packed_Texture"


def test_load_v11_channel_defs():
    cfg = load_config_from_dict(MINIMAL_V11)
    od = cfg.texture_output_definitions[0]
    assert "R" in od.channels and "G" in od.channels and "B" in od.channels and "A" in od.channels
    r_ch = od.channels["R"]
    assert isinstance(r_ch, ChannelDef)
    assert r_ch.source == "Metallic"
    assert r_ch.ch == "R"
    assert r_ch.constant == 0.0
    g_ch = od.channels["G"]
    assert g_ch.invert is True
    assert g_ch.constant == 0.5
    a_ch = od.channels["A"]
    assert a_ch.source == ""
    assert a_ch.constant == 1.0


def test_load_v11_import_settings():
    cfg = load_config_from_dict(MINIMAL_V11)
    imp = cfg.texture_output_definitions[0].import_settings
    assert isinstance(imp, ImportSettings)
    assert imp.compression == "TC_Masks"
    assert imp.lod_group == "TEXTUREGROUP_World"
    assert imp.virtual_texture is False


def test_load_v11_from_jsonc_file():
    """验证从 JSONC 文件（含注释）解析 v1.1 全量字段。"""
    jsonc = """{
  // v1.1 config
  "config_version": "1.1",
  "default_master_material_path": "",
  "default_fallback_import_path": "/Game/Tmp",
  "target_path_template": "/Game/{Category}/{Name}",
  "conflict_policy": "overwrite",
  "asset_naming_template": { "static_mesh": "SM_{Name}" },
  "texture_input_rules": {
    "match_mode": "glob",
    "rules": {
      "BaseColor": { "priority": 10, "patterns": ["*_D.*"] },
    },
  },
  "texture_output_definitions": [
    {
      "enabled": true,
      "output_name": "Diffuse",
      "suffix": "D",
      "channels": {
        "R": { "from": "BaseColor", "ch": "R" },
        "G": { "from": "BaseColor", "ch": "G" },
        "B": { "from": "BaseColor", "ch": "B" },
        "A": { "constant": 1.0 },
      },
    },
  ],
}"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonc", mode="w", encoding="utf-8") as tf:
        tf.write(jsonc)
        path = tf.name
    try:
        cfg = load_config(path)
        assert cfg.config_version == "1.1"
        assert cfg.conflict_policy == "overwrite"
        assert len(cfg.texture_output_definitions) == 1
        assert cfg.texture_output_definitions[0].output_name == "Diffuse"
        assert "BaseColor" in cfg.texture_input_rules.rules
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def test_load_real_prop_jsonc():
    """加载仓库中的真实 Prop.jsonc 并验证关键字段。"""
    prop_path = os.path.join(THIS_DIR, "..", "..", "..", "Config", "AssetCustoms", "Prop.jsonc")
    prop_path = os.path.normpath(prop_path)
    if not os.path.isfile(prop_path):
        pytest.skip(f"Prop.jsonc not found at {prop_path}")
    cfg = load_config(prop_path)
    assert cfg.config_version == "1.1"
    assert cfg.conflict_policy == "version"
    assert cfg.target_path_template == ""
    assert len(cfg.texture_output_definitions) >= 4
    # MRO 打包项
    mro = [d for d in cfg.texture_output_definitions if d.suffix == "MRO"]
    assert len(mro) == 1
    assert mro[0].allow_missing is True
    assert "R" in mro[0].channels
    assert mro[0].channels["R"].source == "Metallic"


def test_backward_compat_texture_merge():
    """确保旧格式（texture_merge + allowed_modes）仍可工作。"""
    data = {
        "texture_merge": {"mode": "multiply", "opacity": 0.75},
        "allowed_modes": ["normal", "multiply"],
    }
    cfg = load_config_from_dict(data)
    from core.textures.layer_merge import BlendMode
    assert cfg.texture_merge.mode == BlendMode.MULTIPLY
    assert abs(cfg.texture_merge.opacity - 0.75) < 1e-6
    assert cfg.allowed_modes == [BlendMode.NORMAL, BlendMode.MULTIPLY]


def test_defaults_when_empty():
    """空字典 -> 全部使用默认值。"""
    cfg = load_config_from_dict({})
    assert cfg.config_version == "1.1"
    assert cfg.texture_output_definitions == []
    assert cfg.texture_input_rules.match_mode == "glob"
    assert cfg.asset_naming_template.static_mesh == "SM_{Name}"
