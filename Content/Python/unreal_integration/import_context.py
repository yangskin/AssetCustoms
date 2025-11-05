from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover
    unreal = None

from core.config.loader import load_config
from core.config.schema import PluginConfig


@dataclass
class ImportContext:
    """导入上下文：打包 FBX 路径 + 当前内容浏览器路径 + 解析后的预设配置。

    - fbx_path: 选中的 FBX 文件绝对路径（Windows 路径接受反斜杠）。
    - content_path: 当前 Content Browser 路径（例如 /Game/Folder），失败回退 /Game。
    - profile: 解析后的配置对象（PluginConfig）。
    - profile_path: 预设配置文件的绝对路径。
    """

    fbx_path: str
    content_path: str
    profile: PluginConfig
    profile_path: str


def _get_content_browser_path() -> str:
    if unreal is None:
        return "/Game"
    try:
        # UE 5.5+: BlueprintFunctionLibrary 不应实例化，直接调用类方法
        p = unreal.EditorUtilityLibrary.get_current_content_browser_path()
        return p or "/Game"
    except Exception:
        return "/Game"


def build_import_context(fbx_path: str, profile_path: str, base: Optional[PluginConfig] = None) -> ImportContext:
    """构建导入上下文：解析预设并采样当前 Content Browser 路径。

    - 使用 core.config.loader.load_config 解析 JSONC/JSON。
    - 可选 base 用于覆盖/合并默认项。
    """
    # 解析预设配置
    profile = load_config(profile_path, base=base)

    # 采样当前内容浏览器路径
    content_path = _get_content_browser_path()

    return ImportContext(
        fbx_path=str(fbx_path),
        content_path=str(content_path),
        profile=profile,
        profile_path=str(profile_path),
    )
