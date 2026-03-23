from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from core.textures.layer_merge import BlendMode


# ---------------------------------------------------------------------------
# 旧版兼容：贴图图层合并默认参数（用于 merge_layers，非通道编排）
# ---------------------------------------------------------------------------

@dataclass
class TextureMergeDefaults:
    mode: BlendMode = BlendMode.NORMAL
    opacity: float = 1.0


# ---------------------------------------------------------------------------
# V1.1 Schema 数据类
# ---------------------------------------------------------------------------

@dataclass
class AssetSubdirectories:
    """可选的资产类型子目录映射。空字符串表示放在 target_path 根目录。"""
    static_mesh: str = ""
    material_instance: str = ""
    texture: str = ""


@dataclass
class AssetNamingTemplate:
    static_mesh: str = "SM_{Name}"
    material_instance: str = "MI_{Name}"
    texture: str = "T_{Name}_{Suffix}"


@dataclass
class TextureInputRule:
    priority: int = 10
    patterns: List[str] = field(default_factory=list)


@dataclass
class TextureInputRules:
    match_mode: str = "glob"  # "glob" | "regex"
    ignore_case: bool = True
    extensions: List[str] = field(
        default_factory=lambda: [".png", ".tga", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"]
    )
    search_roots: List[str] = field(
        default_factory=lambda: ["{DropDir}", "{DropDir}/Textures", "{DropDir}/Maps"]
    )
    rules: Dict[str, TextureInputRule] = field(default_factory=dict)


@dataclass
class ChannelDef:
    """单个输出通道的映射定义。"""
    source: str = ""       # "from" 字段：逻辑源名（BaseColor / Normal / ...）
    ch: str = "R"          # 源通道 R/G/B/A
    constant: Optional[float] = None   # 缺失源时的兜底常量值
    invert: bool = False
    gamma: Optional[float] = None
    remap: Optional[List[float]] = None  # [inMin, inMax, outMin, outMax]


@dataclass
class ImportSettings:
    compression: str = "TC_Default"
    lod_group: str = "TEXTUREGROUP_World"
    srgb: Optional[bool] = None     # None 表示沿用 output_def 级别的 srgb
    virtual_texture: bool = False
    address_x: str = "Wrap"
    address_y: str = "Wrap"
    mip_gen: str = "FromTextureGroup"


@dataclass
class TextureOutputDef:
    """单个输出贴图的完整定义（对应 texture_output_definitions 数组中的一项）。"""
    enabled: bool = True
    output_name: str = ""
    suffix: str = ""
    category: str = "PBR"
    srgb: bool = True
    file_format: str = "PNG"       # PNG | TGA | EXR
    bit_depth: int = 8
    mips: bool = True
    resize: Optional[Dict[str, int]] = None  # {"width": N, "height": N} 或 None
    alpha_premultiplied: bool = False
    material_parameter: str = ""
    allow_missing: bool = False
    normal_space: Optional[str] = None   # "OpenGL" | "DirectX" | None
    flip_green: bool = False
    channels: Dict[str, ChannelDef] = field(default_factory=dict)  # R/G/B/A -> ChannelDef
    import_settings: ImportSettings = field(default_factory=ImportSettings)


@dataclass
class PluginConfig:
    config_version: str = "1.1"

    # 主材质路径（空字符串表示不创建 MIC）
    default_master_material_path: str = ""
    # 回退导入路径
    default_fallback_import_path: str = "/Game/AIGC_Dropoff"
    # 落地目录模板
    target_path_template: str = "/Game/Assets/{Category}/{Name}"
    # 命名冲突策略
    conflict_policy: str = "version"  # "overwrite" | "skip" | "version"

    # 资产命名模板
    asset_naming_template: AssetNamingTemplate = field(default_factory=AssetNamingTemplate)
    # 资产子目录（可选，空字符串=不分子目录）
    asset_subdirectories: AssetSubdirectories = field(default_factory=AssetSubdirectories)
    # 贴图输入识别规则
    texture_input_rules: TextureInputRules = field(default_factory=TextureInputRules)
    # 输出贴图定义列表
    texture_output_definitions: List[TextureOutputDef] = field(default_factory=list)

    # --- 旧版兼容字段 ---
    # 贴图图层合并默认参数（用于 merge_layers）
    texture_merge: TextureMergeDefaults = field(default_factory=TextureMergeDefaults)
    # 允许的混合模式白名单
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
