import os
import sys
import pytest

THIS_DIR = os.path.dirname(__file__)
PYTHON_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from core.config.loader import load_config_from_dict
from core.config.schema import PluginConfig


def test_load_config_from_dict_basic():
    data = {
        "config_version": "2.0",
        "processing": {
            "conflict_policy": "version",
            "texture_definitions": [
                {
                    "enabled": True,
                    "name": "Diffuse",
                    "suffix": "D",
                    "channels": {
                        "R": {"from": "BaseColor", "ch": "R"},
                        "G": {"from": "BaseColor", "ch": "G"},
                        "B": {"from": "BaseColor", "ch": "B"},
                        "A": {"constant": 1.0},
                    },
                }
            ],
        },
    }
    cfg = load_config_from_dict(data)
    assert isinstance(cfg, PluginConfig)
    assert cfg.config_version == "2.0"
    assert cfg.processing.conflict_policy == "version"
    assert len(cfg.processing.texture_definitions) == 1
    assert cfg.processing.texture_definitions[0].name == "Diffuse"


def test_load_config_with_subdirectories():
    data = {
        "output": {
            "subdirectories": {
                "static_mesh": "",
                "material_instance": "Materials",
                "texture": "Textures",
            },
        },
    }
    cfg = load_config_from_dict(data)
    assert cfg.output.subdirectories.static_mesh == ""
    assert cfg.output.subdirectories.material_instance == "Materials"
    assert cfg.output.subdirectories.texture == "Textures"


def test_load_config_without_subdirectories_defaults_empty():
    cfg = load_config_from_dict({})
    assert cfg.output.subdirectories.static_mesh == ""
    assert cfg.output.subdirectories.material_instance == ""
    assert cfg.output.subdirectories.texture == ""
