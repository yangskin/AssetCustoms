"""sp_bridge.py 纯逻辑部分单元测试。

测试范围（🤖 自动化）：
- 2.1 material_info JSON schema + 序列化/反序列化 round-trip
- 2.5 send_to_sp() 数据包组装（build_sp_script）
- 2.6 find_sp_executable() SP 路径发现
"""
import json
import os

import pytest

from unreal_integration.sp_bridge import (
    build_material_info_json,
    parse_material_info_json,
    collect_texture_paths,
    update_texture_export_paths,
    build_sp_script,
    find_sp_executable,
)


# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------
SAMPLE_MATERIALS = [
    {
        "material_name": "MI_Chair_Wood",
        "material_path": "/Game/Materials/MI_Chair_Wood",
        "textures": [
            {
                "texture_property_name": "BaseColor",
                "texture_path": "/Game/Textures/T_Chair_Wood_BCO",
                "texture_export_path": "",
                "texture_name": "T_Chair_Wood_BCO",
            },
            {
                "texture_property_name": "Normal",
                "texture_path": "/Game/Textures/T_Chair_Wood_N",
                "texture_export_path": "",
                "texture_name": "T_Chair_Wood_N",
            },
        ],
    },
    {
        "material_name": "MI_Chair_Metal",
        "material_path": "/Game/Materials/MI_Chair_Metal",
        "textures": [
            {
                "texture_property_name": "BaseColor",
                "texture_path": "/Game/Textures/T_Chair_Metal_BCO",
                "texture_export_path": "",
                "texture_name": "T_Chair_Metal_BCO",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# 2.1 JSON schema + round-trip
# ---------------------------------------------------------------------------
class TestBuildMaterialInfoJson:
    def test_returns_valid_json(self):
        result = build_material_info_json("SM_Chair", "/Game/Meshes/SM_Chair", SAMPLE_MATERIALS)
        data = json.loads(result)
        assert data["static_mesh"] == "SM_Chair"
        assert data["static_mesh_path"] == "/Game/Meshes/SM_Chair"
        assert len(data["materials"]) == 2

    def test_empty_materials(self):
        result = build_material_info_json("SM_Empty", "/Game/SM_Empty", [])
        data = json.loads(result)
        assert data["materials"] == []

    def test_unicode_names(self):
        materials = [{"material_name": "MI_椅子_木头", "material_path": "/Game/MI_椅子", "textures": []}]
        result = build_material_info_json("SM_椅子", "/Game/SM_椅子", materials)
        data = json.loads(result)
        assert data["static_mesh"] == "SM_椅子"
        assert data["materials"][0]["material_name"] == "MI_椅子_木头"


class TestParseMaterialInfoJson:
    def test_roundtrip(self):
        json_str = build_material_info_json("SM_Chair", "/Game/Meshes/SM_Chair", SAMPLE_MATERIALS)
        data = parse_material_info_json(json_str)
        assert data["static_mesh"] == "SM_Chair"
        assert len(data["materials"]) == 2
        assert data["materials"][0]["textures"][0]["texture_property_name"] == "BaseColor"

    def test_missing_static_mesh_raises(self):
        with pytest.raises(ValueError, match="static_mesh"):
            parse_material_info_json('{"materials": []}')

    def test_missing_materials_raises(self):
        with pytest.raises(ValueError, match="materials"):
            parse_material_info_json('{"static_mesh": "x", "static_mesh_path": "/y"}')

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_material_info_json("not json")


# ---------------------------------------------------------------------------
# collect_texture_paths
# ---------------------------------------------------------------------------
class TestCollectTexturePaths:
    def test_extracts_unique_paths(self):
        info = {"materials": SAMPLE_MATERIALS}
        paths = collect_texture_paths(info)
        assert len(paths) == 3
        assert "/Game/Textures/T_Chair_Wood_BCO" in paths
        assert "/Game/Textures/T_Chair_Wood_N" in paths
        assert "/Game/Textures/T_Chair_Metal_BCO" in paths

    def test_deduplicates(self):
        dup_materials = [
            {"material_name": "A", "material_path": "/A", "textures": [
                {"texture_property_name": "BC", "texture_path": "/T/Same", "texture_export_path": "", "texture_name": "Same"},
            ]},
            {"material_name": "B", "material_path": "/B", "textures": [
                {"texture_property_name": "BC", "texture_path": "/T/Same", "texture_export_path": "", "texture_name": "Same"},
            ]},
        ]
        paths = collect_texture_paths({"materials": dup_materials})
        assert len(paths) == 1

    def test_empty_materials(self):
        paths = collect_texture_paths({"materials": []})
        assert len(paths) == 0

    def test_missing_texture_path(self):
        materials = [{"material_name": "A", "material_path": "/A", "textures": [
            {"texture_property_name": "BC", "texture_path": "", "texture_export_path": "", "texture_name": ""},
        ]}]
        paths = collect_texture_paths({"materials": materials})
        assert len(paths) == 0


# ---------------------------------------------------------------------------
# update_texture_export_paths
# ---------------------------------------------------------------------------
class TestUpdateTextureExportPaths:
    def test_updates_paths(self):
        import copy
        info = {"materials": copy.deepcopy(SAMPLE_MATERIALS)}
        export_map = {
            "/Game/Textures/T_Chair_Wood_BCO": "C:/temp/T_Chair_Wood_BCO.tga",
            "/Game/Textures/T_Chair_Wood_N": "C:/temp/T_Chair_Wood_N.tga",
            "/Game/Textures/T_Chair_Metal_BCO": "C:/temp/T_Chair_Metal_BCO.tga",
        }
        result = update_texture_export_paths(info, export_map)
        assert result["materials"][0]["textures"][0]["texture_export_path"] == "C:/temp/T_Chair_Wood_BCO.tga"
        assert result["materials"][0]["textures"][1]["texture_export_path"] == "C:/temp/T_Chair_Wood_N.tga"

    def test_partial_map(self):
        import copy
        info = {"materials": copy.deepcopy(SAMPLE_MATERIALS)}
        export_map = {"/Game/Textures/T_Chair_Wood_BCO": "C:/temp/BCO.tga"}
        result = update_texture_export_paths(info, export_map)
        assert result["materials"][0]["textures"][0]["texture_export_path"] == "C:/temp/BCO.tga"
        assert result["materials"][0]["textures"][1]["texture_export_path"] == ""


# ---------------------------------------------------------------------------
# 2.5 build_sp_script
# ---------------------------------------------------------------------------
class TestBuildSpScript:
    def test_contains_receive_call(self):
        script = build_sp_script('{"test": true}', "C:/temp/model.fbx")
        assert "receive_from_ue" in script

    def test_contains_mesh_path(self):
        script = build_sp_script('{}', "C:/temp/Chair.fbx")
        assert "Chair.fbx" in script

    def test_escapes_backslashes(self):
        script = build_sp_script('{}', "C:\\temp\\model.fbx")
        # 反斜杠应被转义
        assert "C:\\\\temp\\\\model.fbx" in script

    def test_escapes_quotes(self):
        json_str = '{"name": "it\'s a test"}'
        script = build_sp_script(json_str, "C:/temp/m.fbx")
        # 单引号应被转义
        assert "\\'" in script

    def test_script_is_syntactically_valid(self):
        """脚本能被 Python 编译（不执行，仅语法检查）。"""
        json_str = build_material_info_json("SM_Test", "/Game/SM_Test", [])
        script = build_sp_script(json_str, "C:/temp/SM_Test.fbx")
        # compile() 不会执行，只检查语法
        compile(script, "<sp_script>", "exec")

    def test_no_threading_wrapper(self):
        """脚本不使用 threading — SP API 非线程安全。"""
        script = build_sp_script('{}', "C:/temp/m.fbx")
        assert "import threading" not in script
        assert "threading.Thread" not in script

    def test_has_error_handling(self):
        """脚本包含 try/except 异常处理。"""
        script = build_sp_script('{}', "C:/temp/m.fbx")
        assert "try:" in script
        assert "traceback.print_exc()" in script

    def test_adds_sp_plugins_to_path(self):
        """脚本通过 substance_painter_plugins 访问 SPsync 插件。"""
        script = build_sp_script('{}', "C:/temp/m.fbx")
        assert "substance_painter_plugins" in script
        assert "plugins['SPsync']" in script
        assert "receive_from_ue" in script


# ---------------------------------------------------------------------------
# 2.6 find_sp_executable
# ---------------------------------------------------------------------------
class TestFindSpExecutable:
    def test_finds_exe_in_custom_dir(self, tmp_path):
        """自定义目录下找到 EXE。"""
        exe = tmp_path / "sub" / "Adobe Substance 3D Painter.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text("fake")
        result = find_sp_executable(custom_dir=str(tmp_path), default_dir="__nonexist__")
        assert result == str(exe)

    def test_finds_exe_in_default_dir(self, tmp_path):
        """custom_dir 为 None 时回退到 default_dir。"""
        exe = tmp_path / "Adobe Substance 3D Painter.exe"
        exe.write_text("fake")
        result = find_sp_executable(custom_dir=None, default_dir=str(tmp_path))
        assert result == str(exe)

    def test_custom_dir_takes_priority(self, tmp_path):
        """custom_dir 优先于 default_dir。"""
        custom = tmp_path / "custom"
        default = tmp_path / "default"
        for d in (custom, default):
            d.mkdir()
            (d / "Adobe Substance 3D Painter.exe").write_text("fake")
        result = find_sp_executable(custom_dir=str(custom), default_dir=str(default))
        assert str(custom) in result

    def test_returns_none_when_not_found(self, tmp_path):
        """目录存在但无 EXE → 返回 None。"""
        result = find_sp_executable(custom_dir=str(tmp_path), default_dir=str(tmp_path))
        assert result is None

    def test_returns_none_for_nonexistent_dirs(self):
        """目录不存在 → 返回 None。"""
        result = find_sp_executable(custom_dir="__no_such_dir__", default_dir="__no_such_dir2__")
        assert result is None

    def test_case_insensitive_match(self, tmp_path):
        """文件名大小写不敏感匹配。"""
        exe = tmp_path / "ADOBE SUBSTANCE 3D PAINTER.EXE"
        exe.write_text("fake")
        result = find_sp_executable(custom_dir=str(tmp_path), default_dir="__nonexist__")
        assert result is not None

    def test_skips_invalid_custom_falls_to_default(self, tmp_path):
        """custom_dir 无效时自动回退 default_dir。"""
        exe = tmp_path / "Adobe Substance 3D Painter.exe"
        exe.write_text("fake")
        result = find_sp_executable(custom_dir="__invalid__", default_dir=str(tmp_path))
        assert result == str(exe)
