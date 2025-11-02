from typing import Optional, Dict, Any

try:
    import unreal  # type: ignore
except Exception:
    unreal = None

from core.config.loader import load_config_from_dict
from core.config.schema import PluginConfig


def load_project_config(extra: Optional[Dict[str, Any]] = None) -> PluginConfig:
    """
    从 Unreal 项目设置或默认位置加载配置，并与传入的 extra 合并。
    占位实现：可从 .ini 或 EditorSettings 读取键值。
    """
    data: Dict[str, Any] = {}
    # TODO: unreal.SystemLibrary.get_project_directory() + 读取默认 JSON
    if extra:
        data.update(extra)
    return load_config_from_dict(data)
