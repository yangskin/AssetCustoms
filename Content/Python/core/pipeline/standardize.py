"""标准化执行引擎（FR5）：贴图处理、保存、元信息。

纯 Python 核心（不依赖 Unreal），负责：
- FR5.1 贴图处理：根据 output definitions + 匹配映射，用 channel_pack 组装输出贴图
- 法线 flip_green 处理
- 可选 resize
- 按 file_format/bit_depth 保存到指定目录
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.config.schema import PluginConfig, TextureProcessingDef
from core.textures.channel_pack import pack_channels

import logging

logger = logging.getLogger("AssetCustoms")

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore


def _resolve_import_settings(config: PluginConfig, suffix: str) -> Dict:
    """从 output.texture_import_defaults + texture_import_overrides[suffix] 合并导入设置。"""
    defaults = config.output.texture_import_defaults
    settings = {
        "compression": defaults.compression,
        "lod_group": defaults.lod_group,
        "srgb": defaults.srgb,
        "virtual_texture": defaults.virtual_texture,
        "address_x": defaults.address_x,
        "address_y": defaults.address_y,
        "mip_gen": defaults.mip_gen,
        "max_resolution": defaults.max_resolution,
    }
    overrides = config.output.texture_import_overrides.get(suffix, {})
    settings.update(overrides)
    return settings


@dataclass
class ProcessedTexture:
    """单张处理完成的输出贴图信息。"""
    output_name: str
    suffix: str
    file_path: str          # 保存后的磁盘路径
    material_parameter: str  # 对应的材质参数名
    import_settings: Dict    # 供 UE 导入设置使用
    srgb: bool


@dataclass
class StandardizeResult:
    """标准化引擎执行结果。"""
    textures: List[ProcessedTexture] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


def _load_source_images(
    mapping: Dict[str, str],
) -> Dict[str, Any]:
    """从映射加载源贴图为 PIL.Image。

    Args:
        mapping: {逻辑位名: 文件路径} 来自 MatchResult.mapping。

    Returns:
        {逻辑位名: PIL.Image}
    """
    if Image is None:
        raise ImportError("Pillow 未安装")
    sources: Dict[str, Any] = {}
    for slot, path in mapping.items():
        try:
            sources[slot] = Image.open(path).convert("RGBA")
        except Exception as e:
            logger.warning("Failed to load source image for slot '%s': %s — %s", slot, path, e)
    return sources


def _apply_flip_green(img: Any) -> Any:
    """法线贴图 G 通道取反（flip_green）。"""
    if Image is None:
        raise ImportError("Pillow 未安装")
    r, g, b, a = img.split()
    g = g.point(lambda px: 255 - px)
    return Image.merge("RGBA", (r, g, b, a))


def _resize_image(img: Any, resize_spec: Optional[Dict[str, int]]) -> Any:
    """可选缩放。"""
    if resize_spec is None:
        return img
    w = resize_spec.get("width", img.size[0])
    h = resize_spec.get("height", img.size[1])
    if (w, h) == img.size:
        return img
    return img.resize((w, h), resample=getattr(Image, "BILINEAR", 2))


def _apply_max_resolution(img: Any, max_res: Optional[int]) -> Any:
    """max_resolution 上限（仅缩小，不放大）。"""
    if max_res is None or max_res <= 0:
        return img
    w, h = img.size
    new_w = min(w, max_res)
    new_h = min(h, max_res)
    if (new_w, new_h) == (w, h):
        return img
    return img.resize((new_w, new_h), resample=getattr(Image, "BILINEAR", 2))


def _save_image(
    img: Any,
    output_dir: str,
    filename: str,
    file_format: str,
    bit_depth: int,
) -> str:
    """保存图像到磁盘。返回保存路径。"""
    fmt = file_format.upper()
    if fmt == "TGA":
        ext = ".tga"
    elif fmt == "EXR":
        ext = ".exr"
    else:
        ext = ".png"

    path = os.path.join(output_dir, f"{filename}{ext}")
    os.makedirs(output_dir, exist_ok=True)

    if fmt == "PNG" and bit_depth == 16:
        # 16-bit PNG 需要转换为 I;16 模式
        try:
            import numpy as np  # type: ignore
            arr = np.array(img.convert("L")).astype(np.uint16)
            arr = arr * 257  # 8-bit -> 16-bit 映射
            img16 = Image.fromarray(arr, mode="I;16")
            img16.save(path, format="PNG")
        except Exception:
            img.save(path, format="PNG")
    elif fmt == "TGA":
        img.save(path, format="TGA")
    elif fmt == "EXR":
        # EXR 需要额外库支持，先保存为 PNG 作为回退
        try:
            img.save(path, format="EXR")
        except Exception:
            logger.warning("EXR 保存失败，回退为 PNG: %s", path)
            path = path.replace(".exr", ".png")
            img.save(path, format="PNG")
    else:
        img.save(path, format="PNG")

    return path


def process_textures(
    config: PluginConfig,
    mapping: Dict[str, str],
    output_dir: str,
    base_name: str,
    category: str = "Asset",
) -> StandardizeResult:
    """FR5.1：处理所有 enabled 的输出贴图定义。

    Args:
        config: Profile 配置。
        mapping: 逻辑位 -> 源贴图文件路径（来自 MatchResult.mapping）。
        output_dir: 输出目录（通常为隔离区或最终路径）。
        base_name: 资产基础名（用于文件命名）。
        category: Profile 类别。

    Returns:
        StandardizeResult：处理结果。
    """
    if Image is None:
        return StandardizeResult(errors=["Pillow 未安装，无法处理贴图"])

    result = StandardizeResult()
    sources = _load_source_images(mapping)

    for proc_def in config.processing.texture_definitions:
        if not proc_def.enabled:
            continue
        try:
            # 通道编排
            img = pack_channels(proc_def, sources)

            # 法线 flip_green
            if proc_def.flip_green:
                img = _apply_flip_green(img)

            # 可选缩放
            img = _resize_image(img, proc_def.resize)

            # 处理阶段 max_resolution 上限（仅缩小，不放大）
            img = _apply_max_resolution(img, proc_def.max_resolution)

            # 生成文件名
            tex_name = config.output.naming.texture
            tex_name = tex_name.replace("{Name}", base_name)
            tex_name = tex_name.replace("{Suffix}", proc_def.suffix)

            # 保存
            file_path = _save_image(
                img, output_dir, tex_name,
                proc_def.format, proc_def.bit_depth,
            )

            # 合并导入设置
            import_settings_dict = _resolve_import_settings(config, proc_def.suffix)
            if import_settings_dict.get("srgb") is None:
                import_settings_dict["srgb"] = proc_def.srgb

            result.textures.append(ProcessedTexture(
                output_name=proc_def.name,
                suffix=proc_def.suffix,
                file_path=file_path,
                material_parameter=config.output.material.parameter_bindings.get(proc_def.suffix, ""),
                import_settings=import_settings_dict,
                srgb=proc_def.srgb,
            ))

        except Exception as e:
            result.errors.append(f"处理 {proc_def.name} 失败: {e}")

    return result
