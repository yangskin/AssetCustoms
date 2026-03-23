"""测试 Schema v2.0 全量字段解析（从 Prop.jsonc 级别的完整配置加载）。"""
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
    InputConfig,
    TextureInputConfig,
    NamingConfig,
    ChannelDef,
    TextureImportDefaults,
    TextureInputRule,
    TextureProcessingDef,
    ProcessingConfig,
    OutputConfig,
    MaterialOutputConfig,
)


# ---------------------------------------------------------------------------
# 最小 V2.0 字典（覆盖三段式 + 一个完整 texture_definition）
# ---------------------------------------------------------------------------
MINIMAL_V20 = {
    "config_version": "2.0",
    "input": {
        "texture": {
            "match_mode": "regex",
            "ignore_case": False,
            "extensions": [".png", ".tga"],
            "search_roots": ["{DropDir}"],
            "rules": {
                "BaseColor": {"priority": 10, "patterns": [".*_bc.*"]},
                "Normal": {"priority": 9, "patterns": [".*_n$", ".*_normal.*"]},
            },
        },
    },
    "processing": {
        "conflict_policy": "skip",
        "texture_definitions": [
            {
                "enabled": True,
                "name": "Packed_MRO",
                "suffix": "MRO",
                "category": "PBR",
                "srgb": False,
                "format": "PNG",
                "bit_depth": 8,
                "mips": True,
                "allow_missing": True,
                "channels": {
                    "R": {"from": "Metallic", "ch": "R", "constant": 0.0},
                    "G": {"from": "Roughness", "ch": "R", "constant": 0.5, "invert": True},
                    "B": {"from": "AmbientOcclusion", "ch": "R", "constant": 1.0},
                    "A": {"constant": 1.0},
                },
            }
        ],
    },
    "output": {
        "target_path_template": "/Game/{Category}/{Name}",
        "fallback_path": "/Game/Drop",
        "naming": {
            "static_mesh": "SM_{Name}",
            "material_instance": "MI_{Name}",
            "texture": "T_{Name}_{Suffix}",
        },
        "material": {
            "master_material_path": "/Game/M/MM_PBR.MM_PBR",
            "parameter_bindings": {"MRO": "Packed_Texture"},
        },
        "texture_import_defaults": {
            "compression": "TC_Masks",
            "lod_group": "TEXTUREGROUP_World",
            "virtual_texture": False,
        },
    },
}


def test_load_v20_toplevel():
    cfg = load_config_from_dict(MINIMAL_V20)
    assert cfg.config_version == "2.0"
    assert cfg.output.material.master_material_path == "/Game/M/MM_PBR.MM_PBR"
    assert cfg.output.fallback_path == "/Game/Drop"
    assert cfg.output.target_path_template == "/Game/{Category}/{Name}"
    assert cfg.processing.conflict_policy == "skip"


def test_load_v20_naming():
    cfg = load_config_from_dict(MINIMAL_V20)
    assert isinstance(cfg.output.naming, NamingConfig)
    assert cfg.output.naming.static_mesh == "SM_{Name}"
    assert cfg.output.naming.texture == "T_{Name}_{Suffix}"


def test_load_v20_input_rules():
    cfg = load_config_from_dict(MINIMAL_V20)
    tir = cfg.input.texture
    assert isinstance(tir, TextureInputConfig)
    assert tir.match_mode == "regex"
    assert tir.ignore_case is False
    assert tir.extensions == [".png", ".tga"]
    assert "BaseColor" in tir.rules
    assert tir.rules["BaseColor"].priority == 10
    assert tir.rules["BaseColor"].patterns == [".*_bc.*"]
    assert tir.rules["Normal"].priority == 9


def test_load_v20_texture_definitions():
    cfg = load_config_from_dict(MINIMAL_V20)
    assert len(cfg.processing.texture_definitions) == 1
    td = cfg.processing.texture_definitions[0]
    assert isinstance(td, TextureProcessingDef)
    assert td.name == "Packed_MRO"
    assert td.suffix == "MRO"
    assert td.srgb is False
    assert td.allow_missing is True


def test_load_v20_channel_defs():
    cfg = load_config_from_dict(MINIMAL_V20)
    td = cfg.processing.texture_definitions[0]
    assert "R" in td.channels and "G" in td.channels and "B" in td.channels and "A" in td.channels
    r_ch = td.channels["R"]
    assert isinstance(r_ch, ChannelDef)
    assert r_ch.source == "Metallic"
    assert r_ch.ch == "R"
    assert r_ch.constant == 0.0
    g_ch = td.channels["G"]
    assert g_ch.invert is True
    assert g_ch.constant == 0.5
    a_ch = td.channels["A"]
    assert a_ch.source == ""
    assert a_ch.constant == 1.0


def test_load_v20_import_defaults():
    cfg = load_config_from_dict(MINIMAL_V20)
    imp = cfg.output.texture_import_defaults
    assert isinstance(imp, TextureImportDefaults)
    assert imp.compression == "TC_Masks"
    assert imp.lod_group == "TEXTUREGROUP_World"
    assert imp.virtual_texture is False


def test_load_v20_material_bindings():
    cfg = load_config_from_dict(MINIMAL_V20)
    mat = cfg.output.material
    assert isinstance(mat, MaterialOutputConfig)
    assert mat.parameter_bindings["MRO"] == "Packed_Texture"


def test_load_v20_from_jsonc_file():
    """验证从 JSONC 文件（含注释）解析 v2.0 全量字段。"""
    jsonc = """{
  // v2.0 config
  "config_version": "2.0",
  "input": {
    "texture": {
      "match_mode": "glob",
      "rules": {
        "BaseColor": { "priority": 10, "patterns": ["*_D.*"] },
      },
    },
  },
  "processing": {
    "conflict_policy": "overwrite",
    "texture_definitions": [
      {
        "enabled": true,
        "name": "Diffuse",
        "suffix": "D",
        "channels": {
          "R": { "from": "BaseColor", "ch": "R" },
          "G": { "from": "BaseColor", "ch": "G" },
          "B": { "from": "BaseColor", "ch": "B" },
          "A": { "constant": 1.0 },
        },
      },
    ],
  },
  "output": {
    "naming": { "static_mesh": "SM_{Name}" },
  },
}"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonc", mode="w", encoding="utf-8") as tf:
        tf.write(jsonc)
        path = tf.name
    try:
        cfg = load_config(path)
        assert cfg.config_version == "2.0"
        assert cfg.processing.conflict_policy == "overwrite"
        assert len(cfg.processing.texture_definitions) == 1
        assert cfg.processing.texture_definitions[0].name == "Diffuse"
        assert "BaseColor" in cfg.input.texture.rules
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
    assert cfg.config_version == "2.0"
    assert cfg.processing.conflict_policy == "version"
    assert cfg.output.target_path_template == ""
    assert len(cfg.processing.texture_definitions) >= 4
    # MRO 打包项
    mro = [d for d in cfg.processing.texture_definitions if d.suffix == "MRO"]
    assert len(mro) == 1
    assert mro[0].allow_missing is True
    assert "R" in mro[0].channels
    assert mro[0].channels["R"].source == "Metallic"


def test_defaults_when_empty():
    """空字典 -> 全部使用默认值。"""
    cfg = load_config_from_dict({})
    assert cfg.config_version == "2.0"
    assert cfg.processing.texture_definitions == []
    assert cfg.input.texture.match_mode == "glob"
    assert cfg.output.naming.static_mesh == "SM_{Name}"
