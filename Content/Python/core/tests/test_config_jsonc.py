import os
import sys
import tempfile

# 确保可以导入 Content/Python 下的模块
THIS_DIR = os.path.dirname(__file__)
PYTHON_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from core.config.loader import load_config


def test_load_jsonc_with_comments_and_trailing_commas():
    jsonc_text = (
        '{\n'
        '  // comment line\n'
        '  "config_version": "2.0",\n'
        '  "processing": {\n'
        '    "conflict_policy": "version", // inline comment\n'
        '    "texture_definitions": [\n'
        '      {\n'
        '        "name": "Diffuse",\n'
        '        "suffix": "D",\n'
        '        "channels": {\n'
        '          "R": { "from": "BaseColor", "ch": "R" },\n'
        '        },\n'
        '      },\n'
        '    ],\n'
        '  },\n'
        '  "output": {\n'
        '    "target_path_template": "/Game/{Category}/{Name}",\n'
        '  },\n'
        '  /* block comment */\n'
        '}\n'
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonc", mode="w", encoding="utf-8") as tf:
        tf.write(jsonc_text)
        path = tf.name
    try:
        cfg = load_config(path)
        assert cfg.config_version == "2.0"
        assert cfg.processing.conflict_policy == "version"
        assert len(cfg.processing.texture_definitions) == 1
        assert cfg.processing.texture_definitions[0].name == "Diffuse"
        assert cfg.output.target_path_template == "/Game/{Category}/{Name}"
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
