"""通道编排引擎：根据 TextureOutputDef 的 channels 定义，从多张源贴图中
提取指定通道并组装为新的输出贴图。

与 layer_merge（图层叠加/混合模式）不同，channel_pack 是像素搬运 + 变换：
- 从指定逻辑源（BaseColor / Roughness / Metallic …）读取指定通道（R/G/B/A）
- 可选 invert / gamma / remap
- 缺失源时使用 constant 兜底
- 输出一张 RGBA 图像

典型场景：MRO 打包（Metallic→R, Roughness→G, AO→B）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    from core.config.schema import ChannelDef, TextureProcessingDef

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore

try:
    import numpy as np  # type: ignore
except Exception:
    np = None  # type: ignore


def _channel_index(ch: str) -> int:
    """R=0, G=1, B=2, A=3"""
    return {"R": 0, "G": 1, "B": 2, "A": 3}[ch.upper()]


def _apply_transforms(arr: Any, ch_def: ChannelDef) -> Any:
    """对单通道浮点数组应用 invert / remap / gamma。"""
    if ch_def.invert:
        arr = 1.0 - arr
    if ch_def.remap and len(ch_def.remap) == 4:
        in_min, in_max, out_min, out_max = ch_def.remap
        denom = in_max - in_min
        if abs(denom) > 1e-9:
            arr = (arr - in_min) / denom * (out_max - out_min) + out_min
    if ch_def.gamma is not None and ch_def.gamma != 1.0:
        if np is not None:
            arr = np.clip(arr, 0.0, 1.0)
            arr = np.power(arr, ch_def.gamma)
        else:
            arr = max(0.0, min(1.0, arr)) ** ch_def.gamma
    return arr


def pack_channels(
    output_def: TextureProcessingDef,
    sources: Dict[str, Any],
    size: Optional[Tuple[int, int]] = None,
) -> Any:
    """根据 output_def.channels 定义，从 sources 中提取通道并组装输出图像。

    Args:
        output_def: 一个 TextureOutputDef，描述 R/G/B/A 各通道的来源。
        sources: {逻辑源名: PIL.Image} 字典，例如 {"Metallic": img, "Roughness": img, ...}。
                 键名对应 ChannelDef.source（即 JSONC 中的 "from"）。
        size: 输出尺寸 (width, height)。None 则从第一个可用源推断。

    Returns:
        PIL.Image (RGBA)，组装后的输出图像。
    """
    if Image is None:
        raise ImportError("Pillow 未安装，无法执行通道编排")

    # 推断输出尺寸
    if size is None:
        for src_img in sources.values():
            if src_img is not None:
                size = src_img.size
                break
    if size is None:
        size = (1, 1)

    channel_order = ["R", "G", "B", "A"]

    if np is not None:
        return _pack_numpy(output_def, sources, size, channel_order)
    return _pack_pillow(output_def, sources, size, channel_order)


def _pack_numpy(
    output_def: TextureProcessingDef,
    sources: Dict[str, Any],
    size: Tuple[int, int],
    channel_order: list,
) -> Any:
    """numpy 快速路径。"""
    w, h = size
    out = np.zeros((h, w, 4), dtype=np.float32)

    # 缓存已转换的源图像
    src_cache: Dict[str, Any] = {}

    for i, ch_name in enumerate(channel_order):
        ch_def = output_def.channels.get(ch_name)
        if ch_def is None:
            # 未定义的通道：A 默认 1.0，其他默认 0.0
            out[..., i] = 1.0 if ch_name == "A" else 0.0
            continue

        # 尝试从源获取通道像素
        src_img = sources.get(ch_def.source) if ch_def.source else None
        if src_img is not None:
            cache_key = ch_def.source
            if cache_key not in src_cache:
                img = src_img.convert("RGBA")
                if img.size != size:
                    img = img.resize(size, resample=getattr(Image, "BILINEAR", 2))
                src_cache[cache_key] = np.array(img).astype(np.float32) / 255.0
            src_arr = src_cache[cache_key]
            ch_idx = _channel_index(ch_def.ch)
            channel_data = src_arr[..., ch_idx].copy()
            channel_data = _apply_transforms(channel_data, ch_def)
            out[..., i] = np.clip(channel_data, 0.0, 1.0)
        elif ch_def.constant is not None:
            out[..., i] = float(ch_def.constant)
        else:
            out[..., i] = 1.0 if ch_name == "A" else 0.0

    result = (out * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(result, mode="RGBA")


def _pack_pillow(
    output_def: TextureProcessingDef,
    sources: Dict[str, Any],
    size: Tuple[int, int],
    channel_order: list,
) -> Any:
    """纯 Pillow 回退（无 numpy）。"""
    w, h = size
    bands = []

    for ch_name in channel_order:
        ch_def = output_def.channels.get(ch_name)
        if ch_def is None:
            default = 255 if ch_name == "A" else 0
            bands.append(Image.new("L", size, default))
            continue

        src_img = sources.get(ch_def.source) if ch_def.source else None
        if src_img is not None:
            img = src_img.convert("RGBA")
            if img.size != size:
                img = img.resize(size, resample=getattr(Image, "BILINEAR", 2))
            ch_idx = _channel_index(ch_def.ch)
            channel_band = img.split()[ch_idx]

            if ch_def.invert or ch_def.gamma or ch_def.remap:
                # 逐像素变换
                pixels = list(channel_band.getdata())
                out_pixels = []
                for px in pixels:
                    val = px / 255.0
                    if ch_def.invert:
                        val = 1.0 - val
                    if ch_def.remap and len(ch_def.remap) == 4:
                        in_min, in_max, out_min, out_max = ch_def.remap
                        denom = in_max - in_min
                        if abs(denom) > 1e-9:
                            val = (val - in_min) / denom * (out_max - out_min) + out_min
                    if ch_def.gamma is not None and ch_def.gamma != 1.0:
                        val = max(0.0, min(1.0, val)) ** ch_def.gamma
                    out_pixels.append(int(max(0.0, min(1.0, val)) * 255.0 + 0.5))
                channel_band = Image.new("L", size)
                channel_band.putdata(out_pixels)
            bands.append(channel_band)
        elif ch_def.constant is not None:
            val = int(max(0.0, min(1.0, float(ch_def.constant))) * 255.0 + 0.5)
            bands.append(Image.new("L", size, val))
        else:
            default = 255 if ch_name == "A" else 0
            bands.append(Image.new("L", size, default))

    return Image.merge("RGBA", bands)
