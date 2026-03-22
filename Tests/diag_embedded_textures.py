"""诊断脚本：导入 FBX 查看 UE 提取的嵌入贴图资产。

检查 TestStaticMesh.fbx 包含哪些嵌入贴图。
"""
import unreal
import os
import sys

unreal.log("=" * 60)
unreal.log("[DIAG] Embedded Texture Diagnostic")
unreal.log("=" * 60)

# 定位 FBX
_plugin_python_dir = None
for p in sys.path:
    if "AssetCustoms" in p and p.endswith("Python"):
        _plugin_python_dir = p
        break

_content_dir = os.path.dirname(_plugin_python_dir)
_plugin_dir = os.path.dirname(_content_dir)
FBX_PATH = os.path.join(_plugin_dir, "Tests", "TestStaticMesh.fbx")
ISOLATION_PATH = "/Game/_diag_embedded_test"

unreal.log(f"[DIAG] FBX: {FBX_PATH}")
unreal.log(f"[DIAG] Isolation: {ISOLATION_PATH}")

elib = unreal.EditorAssetLibrary

# 清理旧的诊断目录
if elib.does_directory_exist(ISOLATION_PATH):
    elib.delete_directory(ISOLATION_PATH)
    unreal.log("[DIAG] Cleaned old diag directory")

# 导入 FBX（启用 import_textures）
unreal.log("[DIAG] Importing FBX with import_textures=True...")
task = unreal.AssetImportTask()
task.set_editor_property("filename", FBX_PATH)
task.set_editor_property("destination_path", ISOLATION_PATH)
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("replace_existing", True)

fbx_options = unreal.FbxImportUI()
fbx_options.set_editor_property("import_mesh", True)
fbx_options.set_editor_property("import_textures", True)
fbx_options.set_editor_property("import_materials", True)
fbx_options.set_editor_property("import_as_skeletal", False)
task.set_editor_property("options", fbx_options)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

imported = task.get_editor_property("imported_object_paths")
imported_list = list(imported) if imported else []

unreal.log(f"[DIAG] Imported {len(imported_list)} asset(s):")
for i, path in enumerate(imported_list):
    unreal.log(f"[DIAG]   {i}: {path}")

# 列出隔离区中的所有资产
unreal.log("[DIAG] Listing all assets in isolation path...")
all_assets = list(elib.list_assets(ISOLATION_PATH, recursive=True))
unreal.log(f"[DIAG] Found {len(all_assets)} total asset(s):")

for asset_path in all_assets:
    # 加载资产并检查类型
    clean_path = asset_path.split('.')[0] if '.' in asset_path else asset_path
    obj = elib.load_asset(clean_path)
    obj_class = type(obj).__name__ if obj else "UNKNOWN"
    unreal.log(f"[DIAG]   {asset_path} -> {obj_class}")

    # 对 Texture2D，显示更多信息
    if obj and isinstance(obj, unreal.Texture2D):
        try:
            size_x = obj.get_editor_property("blueprint_width") if hasattr(obj, "blueprint_width") else "?"
            size_y = obj.get_editor_property("blueprint_height") if hasattr(obj, "blueprint_height") else "?"
            srgb = obj.get_editor_property("srgb")
            unreal.log(f"[DIAG]     Texture: sRGB={srgb}")
        except Exception as e:
            unreal.log(f"[DIAG]     Texture info error: {e}")

# 测试导出 Texture2D 到磁盘
textures = [p for p in all_assets if "Texture2D" in str(type(elib.load_asset(p.split('.')[0])))]
if not textures:
    # 尝试用 isinstance 检查
    textures = []
    for asset_path in all_assets:
        clean_path = asset_path.split('.')[0] if '.' in asset_path else asset_path
        obj = elib.load_asset(clean_path)
        if obj and isinstance(obj, unreal.Texture2D):
            textures.append(asset_path)

unreal.log(f"[DIAG] Found {len(textures)} Texture2D asset(s)")

if textures:
    # 测试导出第一个贴图
    import tempfile
    export_dir = tempfile.mkdtemp(prefix="diag_export_")
    test_tex_path = textures[0].split('.')[0]
    tex_obj = elib.load_asset(test_tex_path)
    tex_name = test_tex_path.split("/")[-1]
    output_file = os.path.join(export_dir, f"{tex_name}.png")

    unreal.log(f"[DIAG] Testing export of {test_tex_path} to {output_file}...")

    export_task = unreal.AssetExportTask()
    export_task.set_editor_property("object", tex_obj)
    export_task.set_editor_property("filename", output_file)
    export_task.set_editor_property("automated", True)
    export_task.set_editor_property("prompt", False)
    export_task.set_editor_property("replace_identical", True)

    success = unreal.Exporter.run_asset_export_tasks([export_task])
    unreal.log(f"[DIAG] Export result: {success}")

    if os.path.isfile(output_file):
        fsize = os.path.getsize(output_file)
        unreal.log(f"[DIAG] Exported file exists: {output_file} ({fsize} bytes)")
    else:
        # 检查目录下是否有其他文件（出口可能用了不同扩展名）
        files = os.listdir(export_dir)
        unreal.log(f"[DIAG] Export dir contents: {files}")

# 清理诊断资产
unreal.log("[DIAG] Cleaning up...")
if elib.does_directory_exist(ISOLATION_PATH):
    elib.delete_directory(ISOLATION_PATH)

unreal.log("=" * 60)
unreal.log("[DIAG] Diagnostic complete")
unreal.log("=" * 60)
