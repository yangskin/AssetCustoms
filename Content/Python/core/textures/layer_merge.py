from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Tuple, Any

try:
    from PIL import Image  # type: ignore
except Exception:  # Pillow 可选依赖
    Image = None  # type: ignore

try:
    import numpy as np  # type: ignore  # 可选加速
except Exception:
    np = None  # type: ignore


class BlendMode(str, Enum):
    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    ADD = "add"
    SUBTRACT = "subtract"


@dataclass
class Layer:
    image: Any  # Pillow Image；使用 Any 以兼容无 Pillow 类型环境
    opacity: float = 1.0
    mode: BlendMode = BlendMode.NORMAL


def _ensure_image(img: Any, size: Optional[Tuple[int, int]]) -> Any:
    if size and img.size != size:
        # 2 对应 BILINEAR，避免直接依赖新版 Pillow 常量
        return img.resize(size, resample=getattr(Image, "BILINEAR", 2))
    return img


def merge_layers(
    layers: Iterable[Layer],
    size: Optional[Tuple[int, int]] = None,
    background: Tuple[int, int, int, int] = (0, 0, 0, 0),
) -> Any:
    """
    纯 Python 图层合并。优先使用 Pillow + numpy；在无 numpy 环境下回退到逐像素实现（较慢）。
    - layers: 图层序列（从下到上）
    - size: 目标尺寸（不传则以首层尺寸为准）
    - background: RGBA 背景
    """
    if Image is None:
        raise ImportError("Pillow 未安装，无法执行图层合并")

    layers = list(layers)
    if not layers:
        return Image.new("RGBA", size or (1, 1), background)

    if size is None:
        size = layers[0].image.size

    # 规范化尺寸和模式
    norm = [Layer(_ensure_image(l.image.convert("RGBA"), size), l.opacity, l.mode) for l in layers]
    base = Image.new("RGBA", size, background)

    if np is None:
        # 慢速回退：使用 Image.alpha_composite 叠加，仅支持 NORMAL + 不透明度
        for l in norm:
            if l.opacity < 1.0:
                top = l.image.copy()
                a = top.split()[-1].point(lambda px: int(px * l.opacity))
                top.putalpha(a)
            else:
                top = l.image
            base = Image.alpha_composite(base, top)
        return base

    # 快速路径：numpy
    base_np = np.array(base).astype(np.float32) / 255.0
    for l in norm:
        top_np = np.array(l.image).astype(np.float32) / 255.0
        tr, tg, tb, ta = top_np[..., 0], top_np[..., 1], top_np[..., 2], top_np[..., 3]
        br, bg, bb, ba = base_np[..., 0], base_np[..., 1], base_np[..., 2], base_np[..., 3]

        # 应用图层不透明度
        ta = ta * float(max(0.0, min(1.0, l.opacity)))

        def blend(c_b, c_t, mode: BlendMode):
            if mode == BlendMode.NORMAL:
                return c_t
            if mode == BlendMode.MULTIPLY:
                return c_b * c_t
            if mode == BlendMode.SCREEN:
                return 1.0 - (1.0 - c_b) * (1.0 - c_t)
            if mode == BlendMode.OVERLAY:
                return np.where(c_b <= 0.5, 2 * c_b * c_t, 1 - 2 * (1 - c_b) * (1 - c_t))
            if mode == BlendMode.ADD:
                return np.clip(c_b + c_t, 0.0, 1.0)
            if mode == BlendMode.SUBTRACT:
                return np.clip(c_b - c_t, 0.0, 1.0)
            return c_t

        Cr = blend(br, tr, l.mode)
        Cg = blend(bg, tg, l.mode)
        Cb = blend(bb, tb, l.mode)

        # 标准 alpha 合成
        out_a = ta + ba * (1 - ta)
        # 避免除零
        eps = 1e-6
        out_r = (Cr * ta + br * ba * (1 - ta)) / (out_a + eps)
        out_g = (Cg * ta + bg * ba * (1 - ta)) / (out_a + eps)
        out_b = (Cb * ta + bb * ba * (1 - ta)) / (out_a + eps)

        base_np = np.stack([out_r, out_g, out_b, out_a], axis=-1)
        base_np = np.clip(base_np, 0.0, 1.0)

    out = (base_np * 255.0 + 0.5).astype("uint8")
    return Image.fromarray(out, mode="RGBA")
