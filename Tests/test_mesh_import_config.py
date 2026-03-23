"""MeshImportConfig 解析与往返测试（纯 Python，无需 Unreal）。"""
import sys
import os

# 将 Content/Python 加入 sys.path 以便直接导入
_CONTENT_PY = os.path.join(os.path.dirname(__file__), "..", "Content", "Python")
sys.path.insert(0, os.path.normpath(_CONTENT_PY))

from core.config.schema import MeshImportConfig, ProcessingConfig
from core.config.loader import _parse_mesh_import, load_config


def test_parse_mesh_import_defaults():
    """空字典应返回全部默认值。"""
    cfg = _parse_mesh_import({})
    assert cfg.import_uniform_scale == 1.0
    assert cfg.import_as_skeletal is False
    assert cfg.normal_import_method == "ImportNormalsAndTangents"
    assert cfg.normal_generation_method == "MikkTSpace"
    assert cfg.compute_weighted_normals is True
    assert cfg.vertex_color_import_option == "Replace"
    assert cfg.import_animations is False
    assert cfg.auto_generate_collision is True
    assert cfg.combine_meshes is True
    assert cfg.remove_degenerates is True
    assert cfg.build_nanite is False
    assert cfg.build_reversed_index_buffer is True
    assert cfg.generate_lightmap_u_vs is True
    assert cfg.convert_scene is True
    assert cfg.convert_scene_unit is True
    assert cfg.force_front_x_axis is False
    assert cfg.import_mesh_lods is False
    assert cfg.static_mesh_lod_group == "None"
    assert cfg.import_materials is True
    assert cfg.import_textures is True
    assert cfg.reorder_material_to_fbx_order is True
    # SkeletalMesh 专有默认值
    assert cfg.skeleton_path == ""
    assert cfg.create_physics_asset is True
    assert cfg.import_morph_targets is True
    assert cfg.import_meshes_in_bone_hierarchy is True
    assert cfg.update_skeleton_reference_pose is False
    assert cfg.use_t0_as_ref_pose is False
    assert cfg.preserve_smoothing_groups is True
    assert cfg.import_content_type == "All"


def test_parse_mesh_import_overrides():
    """自定义值应正确覆盖默认值。"""
    data = {
        "import_uniform_scale": 2.54,
        "import_as_skeletal": True,
        "normal_import_method": "ComputeNormals",
        "normal_generation_method": "BuiltIn",
        "compute_weighted_normals": False,
        "vertex_color_import_option": "Override",
        "vertex_override_color": [128, 64, 32, 200],
        "import_animations": True,
        "auto_generate_collision": False,
        "combine_meshes": False,
        "build_nanite": True,
        "generate_lightmap_u_vs": False,
        "force_front_x_axis": True,
        "import_rotation": [90.0, 0.0, 0.0],
        "import_translation": [100.0, 200.0, 300.0],
        "import_mesh_lods": True,
        "static_mesh_lod_group": "LargeWorld",
    }
    cfg = _parse_mesh_import(data)
    assert cfg.import_uniform_scale == 2.54
    assert cfg.import_as_skeletal is True
    assert cfg.normal_import_method == "ComputeNormals"
    assert cfg.normal_generation_method == "BuiltIn"
    assert cfg.compute_weighted_normals is False
    assert cfg.vertex_color_import_option == "Override"
    assert cfg.vertex_override_color == [128, 64, 32, 200]
    assert cfg.import_animations is True
    assert cfg.auto_generate_collision is False
    assert cfg.combine_meshes is False
    assert cfg.build_nanite is True
    assert cfg.generate_lightmap_u_vs is False
    assert cfg.force_front_x_axis is True
    assert cfg.import_rotation == [90.0, 0.0, 0.0]
    assert cfg.import_translation == [100.0, 200.0, 300.0]
    assert cfg.import_mesh_lods is True
    assert cfg.static_mesh_lod_group == "LargeWorld"


def test_vertex_override_color_rgb_only():
    """3-元素颜色列表应自动补 A=255。"""
    cfg = _parse_mesh_import({"vertex_override_color": [255, 0, 128]})
    assert cfg.vertex_override_color == [255, 0, 128, 255]


def test_parse_skeletal_overrides():
    """SkeletalMesh 专有字段应正确覆盖默认值。"""
    data = {
        "import_as_skeletal": True,
        "skeleton_path": "/Game/Characters/SK_Mannequin_Skeleton",
        "create_physics_asset": False,
        "import_morph_targets": False,
        "import_meshes_in_bone_hierarchy": False,
        "update_skeleton_reference_pose": True,
        "use_t0_as_ref_pose": True,
        "preserve_smoothing_groups": False,
        "import_content_type": "Geometry",
    }
    cfg = _parse_mesh_import(data)
    assert cfg.import_as_skeletal is True
    assert cfg.skeleton_path == "/Game/Characters/SK_Mannequin_Skeleton"
    assert cfg.create_physics_asset is False
    assert cfg.import_morph_targets is False
    assert cfg.import_meshes_in_bone_hierarchy is False
    assert cfg.update_skeleton_reference_pose is True
    assert cfg.use_t0_as_ref_pose is True
    assert cfg.preserve_smoothing_groups is False
    assert cfg.import_content_type == "Geometry"


def test_full_config_roundtrip():
    """通过 Prop.jsonc 验证端到端加载。"""
    prop_path = os.path.join(
        os.path.dirname(__file__), "..", "Content", "Config", "AssetCustoms", "Prop.jsonc"
    )
    if not os.path.exists(prop_path):
        return  # 跳过：配置文件不存在
    cfg = load_config(prop_path)
    mi = cfg.processing.mesh_import
    assert isinstance(mi, MeshImportConfig)
    assert mi.import_uniform_scale == 1.0
    assert mi.auto_generate_collision is True
    assert mi.vertex_color_import_option == "Ignore"
    assert mi.import_animations is False


if __name__ == "__main__":
    test_parse_mesh_import_defaults()
    test_parse_mesh_import_overrides()
    test_vertex_override_color_rgb_only()
    test_full_config_roundtrip()
    print("All MeshImportConfig tests passed!")
