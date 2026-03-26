from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ===========================================================================
# Config v2.0 — 三段式管线模型（Input → Processing → Output）
# 设计文档：docs/decisions/ADR-0002-config-v2-pipeline-model.md
# ===========================================================================


# ---------------------------------------------------------------------------
# 共享基础类型
# ---------------------------------------------------------------------------

@dataclass
class TextureInputRule:
    priority: int = 10
    patterns: List[str] = field(default_factory=list)


@dataclass
class ChannelDef:
    """单个输出通道的映射定义。"""
    source: str = ""       # "from" 字段：逻辑源名（BaseColor / Normal / ...）
    ch: str = "R"          # 源通道 R/G/B/A
    constant: Optional[float] = None   # 缺失源时的兜底常量值
    invert: bool = False
    gamma: Optional[float] = None
    remap: Optional[List[float]] = None  # [inMin, inMax, outMin, outMax]


# ---------------------------------------------------------------------------
# 阶段一：传入（Input）— "拿到什么、怎么识别"
# ---------------------------------------------------------------------------

@dataclass
class TextureInputConfig:
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
class InputConfig:
    texture: TextureInputConfig = field(default_factory=TextureInputConfig)


# ---------------------------------------------------------------------------
# 阶段二：处理（Processing）— "怎么加工"
# ---------------------------------------------------------------------------

@dataclass
class TextureProcessingDef:
    """单个输出贴图的处理定义（通道编排 + 格式参数）。"""
    enabled: bool = True
    name: str = ""
    suffix: str = ""
    category: str = "PBR"
    channels: Dict[str, ChannelDef] = field(default_factory=dict)
    flip_green: bool = False
    normal_space: Optional[str] = None   # "OpenGL" | "DirectX" | None
    allow_missing: bool = False
    format: str = "PNG"                  # "PNG" | "TGA" | "EXR"
    bit_depth: int = 8
    srgb: bool = True
    mips: bool = True
    resize: Optional[Dict[str, int]] = None
    alpha_premultiplied: bool = False
    max_resolution: Optional[int] = None  # 正方形最大分辨率, POT (e.g. 2048)


@dataclass
class MeshImportConfig:
    """FBX 模型导入设置。设计文档：docs/decisions/ADR-0003-mesh-import-settings.md"""

    # ── 基础 ──
    import_uniform_scale: float = 1.0
    import_as_skeletal: bool = False

    # ── 法线与切线 ──
    normal_import_method: str = "ImportNormalsAndTangents"
    # "ComputeNormals" | "ImportNormals" | "ImportNormalsAndTangents"
    normal_generation_method: str = "MikkTSpace"
    # "BuiltIn" | "MikkTSpace"
    compute_weighted_normals: bool = True

    # ── 顶点色 ──
    vertex_color_import_option: str = "Replace"
    # "Replace" | "Ignore" | "Override"
    vertex_override_color: Optional[List[int]] = None  # [R,G,B,A] 0-255, Override 模式专用

    # ── 动画 ──
    import_animations: bool = False

    # ── 碰撞与几何 ──
    auto_generate_collision: bool = True
    combine_meshes: bool = True
    remove_degenerates: bool = True
    build_nanite: bool = False
    build_reversed_index_buffer: bool = True
    generate_lightmap_u_vs: bool = True

    # ── 坐标变换 ──
    convert_scene: bool = True
    convert_scene_unit: bool = True
    force_front_x_axis: bool = False
    import_rotation: Optional[List[float]] = None   # [Pitch, Yaw, Roll]
    import_translation: Optional[List[float]] = None # [X, Y, Z]

    # ── LOD ──
    import_mesh_lods: bool = False
    static_mesh_lod_group: str = "None"

    # ── 材质/贴图导入 ──
    import_materials: bool = True
    import_textures: bool = True
    reorder_material_to_fbx_order: bool = True

    # ── SkeletalMesh 专有（仅 import_as_skeletal=True 时生效）──
    skeleton_path: str = ""
    create_physics_asset: bool = True
    import_morph_targets: bool = True
    import_meshes_in_bone_hierarchy: bool = True
    update_skeleton_reference_pose: bool = False
    use_t0_as_ref_pose: bool = False
    preserve_smoothing_groups: bool = True
    import_content_type: str = "All"  # "All" | "Geometry" | "SkinningWeights"


@dataclass
class ProcessingConfig:
    conflict_policy: str = "version"  # "overwrite" | "skip" | "version"
    mesh_import: MeshImportConfig = field(default_factory=MeshImportConfig)
    texture_definitions: List[TextureProcessingDef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 阶段三：交付（Output）— "放哪里、叫什么、UE 怎么设"
# ---------------------------------------------------------------------------

@dataclass
class SubdirectoriesConfig:
    static_mesh: str = ""
    material_instance: str = ""
    texture: str = ""


@dataclass
class NamingConfig:
    static_mesh: str = "SM_{Name}"
    material_instance: str = "MI_{Name}"
    texture: str = "T_{Name}_{Suffix}"


@dataclass
class MaterialOutputConfig:
    master_material_path: str = ""
    parameter_bindings: Dict[str, str] = field(default_factory=dict)  # suffix -> MI param name


@dataclass
class TextureImportDefaults:
    compression: str = "TC_Default"
    lod_group: str = "TEXTUREGROUP_World"
    srgb: Optional[bool] = None     # None = 沿用 processing 定义的 srgb
    virtual_texture: bool = False
    address_x: str = "Wrap"
    address_y: str = "Wrap"
    mip_gen: str = "FromTextureGroup"
    max_resolution: Optional[int] = None  # 交付最大尺寸, POT (e.g. 1024)


@dataclass
class OutputConfig:
    target_path_template: str = ""
    fallback_path: str = "/Game/AIGC_Dropoff"
    subdirectories: SubdirectoriesConfig = field(default_factory=SubdirectoriesConfig)
    naming: NamingConfig = field(default_factory=NamingConfig)
    material: MaterialOutputConfig = field(default_factory=MaterialOutputConfig)
    texture_import_defaults: TextureImportDefaults = field(default_factory=TextureImportDefaults)
    texture_import_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 顶层配置
# ---------------------------------------------------------------------------

@dataclass
class PluginConfig:
    config_version: str = "2.0"
    input: InputConfig = field(default_factory=InputConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
