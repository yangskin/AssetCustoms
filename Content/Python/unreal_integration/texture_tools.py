from typing import Iterable, Optional, Tuple

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover - 允许在非 Unreal 环境下导入
    unreal = None

from core.textures.layer_merge import Layer, BlendMode, merge_layers
from core.config.schema import PluginConfig


def _texture_to_pillow(tex):
    """
    将 Unreal Texture2D 读取为 Pillow Image（RGBA）。
    占位实现：实际需使用 unreal Python API 读取像素。
    """
    if unreal is None:
        raise RuntimeError("Unreal Python 环境不可用")
    raise NotImplementedError("TODO: 从 Texture2D 提取像素并转为 Pillow Image")


def _pillow_to_texture(img, name_hint: str):
    """
    将 Pillow Image 写回 Unreal 纹理/RenderTarget。
    占位实现：实际需使用 unreal Python API 写入像素。
    """
    if unreal is None:
        raise RuntimeError("Unreal Python 环境不可用")
    raise NotImplementedError("TODO: 将 Pillow Image 写入到新的 Texture2D/RenderTarget")


def merge_textures_in_unreal(
    textures: Iterable,  # Iterable[unreal.Texture2D]
    modes: Iterable[BlendMode],
    opacities: Iterable[float],
    output_name: str,
    cfg: Optional[PluginConfig] = None,
    size: Optional[Tuple[int, int]] = None,
):
    """
    在 Unreal 中合并多张 Texture2D：
    - 读取像素 -> 核心合并 -> 写回新纹理
    """
    cfg = cfg or PluginConfig()
    from PIL import Image  # 延迟导入以提供更清晰错误

    layers = []
    for tex, mode, opacity in zip(textures, modes, opacities):
        pil = _texture_to_pillow(tex)
        layers.append(Layer(pil, float(opacity), BlendMode(mode)))

    result = merge_layers(layers, size=size)
    return _pillow_to_texture(result, output_name)
