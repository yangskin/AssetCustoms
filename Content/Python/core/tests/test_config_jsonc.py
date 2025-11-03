import os
import sys
import tempfile

# 确保可以导入 Content/Python 下的模块
THIS_DIR = os.path.dirname(__file__)
PYTHON_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

from core.config.loader import load_config
from core.textures.layer_merge import BlendMode


def test_load_jsonc_with_comments_and_trailing_commas():
    jsonc_text = (
        '{\n'
        '  // comment line\n'
        '  "texture_merge": {\n'
        '    "mode": "overlay", // inline comment\n'
        '    "opacity": 0.6,\n'
        '  },\n'
        '  "allowed_modes": [\n'
        '    "normal",\n'
        '    "overlay", // trailing comma below\n'
        '  ],\n'
        '  /* block comment */\n'
        '}\n'
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonc", mode="w", encoding="utf-8") as tf:
        tf.write(jsonc_text)
        path = tf.name
    try:
        cfg = load_config(path)
        assert cfg.texture_merge.mode == BlendMode.OVERLAY
        assert abs(cfg.texture_merge.opacity - 0.6) < 1e-6
        assert BlendMode.NORMAL in cfg.allowed_modes
        assert BlendMode.OVERLAY in cfg.allowed_modes
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
