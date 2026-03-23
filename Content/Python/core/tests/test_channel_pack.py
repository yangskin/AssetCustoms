"""测试通道编排引擎 channel_pack。"""
import os
import sys
import pytest

THIS_DIR = os.path.dirname(__file__)
PYTHON_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)

try:
    from PIL import Image
except Exception:
    Image = None  # type: ignore

from core.config.schema import ChannelDef, TextureProcessingDef
from core.textures.channel_pack import pack_channels
import core.textures.channel_pack as channel_pack_mod

pytestmark = pytest.mark.skipif(Image is None, reason="Pillow 未安装，跳过通道编排测试")


def solid(color, size=(4, 4)):
    """创建纯色 RGBA 图像。"""
    return Image.new("RGBA", size, color)


def _make_output_def(channels_dict):
    """从简化字典快速构建 TextureOutputDef。"""
    channels = {}
    for k, v in channels_dict.items():
        channels[k] = ChannelDef(
            source=v.get("from", ""),
            ch=v.get("ch", "R"),
            constant=v.get("constant"),
            invert=v.get("invert", False),
            gamma=v.get("gamma"),
            remap=v.get("remap"),
        )
    return TextureProcessingDef(channels=channels)


# --- 基础：MRO 打包 ---

def test_mro_pack_basic():
    """将独立的 Metallic/Roughness/AO 打包到 RGB。"""
    metallic = solid((200, 0, 0, 255))   # R=200
    roughness = solid((0, 128, 0, 255))  # G=128
    ao = solid((0, 0, 64, 255))          # B=64

    od = _make_output_def({
        "R": {"from": "Metallic", "ch": "R"},
        "G": {"from": "Roughness", "ch": "G"},
        "B": {"from": "AmbientOcclusion", "ch": "B"},
        "A": {"constant": 1.0},
    })

    result = pack_channels(od, {
        "Metallic": metallic,
        "Roughness": roughness,
        "AmbientOcclusion": ao,
    })
    px = result.getpixel((0, 0))
    assert px[0] == 200  # Metallic R -> output R
    assert px[1] == 128  # Roughness G -> output G
    assert px[2] == 64   # AO B -> output B
    assert px[3] == 255  # constant 1.0


def test_constant_fallback():
    """源缺失时使用 constant 兜底。"""
    od = _make_output_def({
        "R": {"from": "Missing", "ch": "R", "constant": 0.0},
        "G": {"from": "Missing", "ch": "R", "constant": 0.5},
        "B": {"from": "Missing", "ch": "R", "constant": 1.0},
        "A": {"constant": 1.0},
    })
    result = pack_channels(od, {}, size=(1, 1))
    px = result.getpixel((0, 0))
    assert px[0] == 0
    assert px[1] == 128  # 0.5 * 255 ≈ 128
    assert px[2] == 255
    assert px[3] == 255


def test_invert():
    """验证 invert 变换。"""
    white = solid((255, 255, 255, 255))
    od = _make_output_def({
        "R": {"from": "Src", "ch": "R", "invert": True},
        "G": {"from": "Src", "ch": "G"},
        "B": {"constant": 0.0},
        "A": {"constant": 1.0},
    })
    result = pack_channels(od, {"Src": white}, size=(1, 1))
    px = result.getpixel((0, 0))
    assert px[0] == 0    # 1.0 inverted -> 0.0
    assert px[1] == 255  # not inverted


def test_resize():
    """源图尺寸与目标不同时正确缩放。"""
    big = solid((100, 200, 50, 255), size=(8, 8))
    od = _make_output_def({
        "R": {"from": "Src", "ch": "R"},
        "G": {"from": "Src", "ch": "G"},
        "B": {"from": "Src", "ch": "B"},
        "A": {"from": "Src", "ch": "A"},
    })
    result = pack_channels(od, {"Src": big}, size=(2, 2))
    assert result.size == (2, 2)
    px = result.getpixel((0, 0))
    assert px[0] == 100
    assert px[1] == 200


def test_undefined_channel_defaults():
    """未定义的通道使用默认值：A=255，其他=0。"""
    od = TextureProcessingDef(channels={})
    result = pack_channels(od, {}, size=(1, 1))
    px = result.getpixel((0, 0))
    assert px[0] == 0    # R default
    assert px[1] == 0    # G default
    assert px[2] == 0    # B default
    assert px[3] == 255  # A default


def test_pillow_fallback_path(monkeypatch):
    """无 numpy 时回退到纯 Pillow 路径。"""
    monkeypatch.setattr(channel_pack_mod, "np", None, raising=False)

    metallic = solid((200, 0, 0, 255))
    roughness = solid((0, 128, 0, 255))

    od = _make_output_def({
        "R": {"from": "Metallic", "ch": "R"},
        "G": {"from": "Roughness", "ch": "G"},
        "B": {"constant": 0.0},
        "A": {"constant": 1.0},
    })
    result = pack_channels(od, {
        "Metallic": metallic,
        "Roughness": roughness,
    })
    px = result.getpixel((0, 0))
    assert px[0] == 200
    assert px[1] == 128
    assert px[2] == 0
    assert px[3] == 255


def test_remap():
    """验证 remap 变换 [0,1] -> [0.5,1.0]。"""
    gray = solid((128, 128, 128, 255), size=(1, 1))  # ~0.502
    od = _make_output_def({
        "R": {"from": "Src", "ch": "R", "remap": [0.0, 1.0, 0.5, 1.0]},
        "G": {"constant": 0.0},
        "B": {"constant": 0.0},
        "A": {"constant": 1.0},
    })
    result = pack_channels(od, {"Src": gray}, size=(1, 1))
    px = result.getpixel((0, 0))
    # 128/255 ≈ 0.502 -> remap -> 0.5 + 0.502*0.5 ≈ 0.751 -> ~191
    assert 189 <= px[0] <= 193
