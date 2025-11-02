import json
from typing import Any, Dict, Optional, Union
from core.textures.layer_merge import BlendMode
from .schema import PluginConfig, TextureMergeDefaults


def _merge_dict(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d)
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)  # type: ignore[index]
        else:
            out[k] = v
    return out


def load_config_from_dict(data: Dict[str, Any], base: Optional[PluginConfig] = None) -> PluginConfig:
    cfg = base or PluginConfig()
    tm = data.get("texture_merge", {}) or {}
    if tm:
        mode = tm.get("mode", getattr(cfg.texture_merge.mode, "value", cfg.texture_merge.mode))
        opacity = tm.get("opacity", cfg.texture_merge.opacity)
        cfg.texture_merge = TextureMergeDefaults(
            mode=BlendMode(mode) if isinstance(mode, str) else mode,
            opacity=float(opacity),
        )
    allowed = data.get("allowed_modes")
    if allowed:
        cfg.allowed_modes = [BlendMode(m) if isinstance(m, str) else m for m in allowed]
    return cfg


def load_config(src: Union[str, Dict[str, Any]], base: Optional[PluginConfig] = None) -> PluginConfig:
    """
    从文件路径（.json）或字典载入配置，并合并到默认配置。
    """
    if isinstance(src, dict):
        return load_config_from_dict(src, base)
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_config_from_dict(data, base)
