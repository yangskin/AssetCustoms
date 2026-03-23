import os
import sys
import pytest

THIS_DIR = os.path.dirname(__file__)
PYTHON_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from core.config.loader import load_config_from_dict
from core.config.schema import PluginConfig
from core.textures.layer_merge import BlendMode


def test_load_config_from_dict_basic():
    data = {
        "texture_merge": {
            "mode": "multiply",
            "opacity": 0.75,
        },
        "allowed_modes": ["normal", "multiply"],
    }
    cfg = load_config_from_dict(data)
    assert isinstance(cfg, PluginConfig)
    assert cfg.texture_merge.mode == BlendMode.MULTIPLY
    assert abs(cfg.texture_merge.opacity - 0.75) < 1e-6
    assert cfg.allowed_modes == [BlendMode.NORMAL, BlendMode.MULTIPLY]


def test_load_config_with_subdirectories():
    data = {
        "asset_subdirectories": {
            "static_mesh": "",
            "material_instance": "Materials",
            "texture": "Textures",
        },
    }
    cfg = load_config_from_dict(data)
    assert cfg.asset_subdirectories.static_mesh == ""
    assert cfg.asset_subdirectories.material_instance == "Materials"
    assert cfg.asset_subdirectories.texture == "Textures"


def test_load_config_without_subdirectories_defaults_empty():
    cfg = load_config_from_dict({})
    assert cfg.asset_subdirectories.static_mesh == ""
    assert cfg.asset_subdirectories.material_instance == ""
    assert cfg.asset_subdirectories.texture == ""
