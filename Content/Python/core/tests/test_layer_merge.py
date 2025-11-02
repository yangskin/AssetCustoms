import os
import sys
import math
import types
import pytest

# 确保可以导入 Content/Python 下的模块
THIS_DIR = os.path.dirname(__file__)
PYTHON_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

try:
    from PIL import Image
except Exception:
    Image = None  # type: ignore

from core.textures.layer_merge import Layer, BlendMode, merge_layers
import core.textures.layer_merge as layer_merge_mod

pytestmark = pytest.mark.skipif(Image is None, reason="Pillow 未安装，跳过图层合并测试")


def solid_rgba(color, size=(1, 1)):
    r, g, b, a = color
    return Image.new("RGBA", size, (r, g, b, a))


def test_normal_alpha_composite():
    base = solid_rgba((255, 0, 0, 255))  # 红，完全不透明
    top = solid_rgba((0, 255, 0, 128))   # 绿，半透明

    out = merge_layers([
        Layer(base, 1.0, BlendMode.NORMAL),
        Layer(top, 1.0, BlendMode.NORMAL),
    ])

    px = out.getpixel((0, 0))
    # 期望：r≈128, g≈128, b=0, a=255
    assert px[0] in (127, 128), px
    assert px[1] in (127, 128), px
    assert px[2] == 0, px
    assert px[3] == 255, px


def test_multiply_gray():
    base = solid_rgba((128, 128, 128, 255))
    top = solid_rgba((128, 128, 128, 255))
    out = merge_layers([
        Layer(base, 1.0, BlendMode.NORMAL),
        Layer(top, 1.0, BlendMode.MULTIPLY),
    ])
    px = out.getpixel((0, 0))
    # 128/255 * 128/255 ≈ 0.25 -> 64
    assert px[:3] == (64, 64, 64)
    assert px[3] == 255


def test_resize_to_target():
    base = solid_rgba((0, 0, 255, 255), size=(2, 2))
    top = solid_rgba((0, 0, 0, 0), size=(1, 1))
    out = merge_layers([
        Layer(base, 1.0, BlendMode.NORMAL),
        Layer(top, 1.0, BlendMode.NORMAL),
    ], size=(2, 2))
    assert out.size == (2, 2)


def test_fallback_without_numpy(monkeypatch):
    base = solid_rgba((255, 0, 0, 255))
    top = solid_rgba((0, 255, 0, 128))

    # 强制触发无 numpy 路径
    monkeypatch.setattr(layer_merge_mod, "np", None, raising=False)

    out = merge_layers([
        Layer(base, 1.0, BlendMode.NORMAL),
        Layer(top, 1.0, BlendMode.NORMAL),
    ])
    px = out.getpixel((0, 0))
    assert px[0] in (127, 128)
    assert px[1] in (127, 128)
    assert px[2] == 0
    assert px[3] == 255
