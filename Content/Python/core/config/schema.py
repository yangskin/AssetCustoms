from dataclasses import dataclass, field
from typing import List
from core.textures.layer_merge import BlendMode


@dataclass
class TextureMergeDefaults:
    mode: BlendMode = BlendMode.NORMAL
    opacity: float = 1.0


@dataclass
class PluginConfig:
    # 贴图合并默认参数
    texture_merge: TextureMergeDefaults = field(default_factory=TextureMergeDefaults)
    # 允许的混合模式白名单（可用于 UI 或校验）
    allowed_modes: List[BlendMode] = field(
        default_factory=lambda: [
            BlendMode.NORMAL,
            BlendMode.MULTIPLY,
            BlendMode.SCREEN,
            BlendMode.OVERLAY,
            BlendMode.ADD,
            BlendMode.SUBTRACT,
        ]
    )
