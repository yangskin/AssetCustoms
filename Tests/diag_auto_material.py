"""诊断脚本：分析 FBX 导入自动生成的材质，读取贴图-通道绑定。

调查：
1. 自动材质类型（Material / MaterialInstanceConstant）
2. 贴图如何绑定到材质通道
3. 可用 API 路径

执行：remote-execute.py --file diag_auto_material.py
"""
import unreal
import os
import sys
import traceback

unreal.log("=" * 60)
unreal.log("[DIAG-MAT] Auto-Material Texture Binding Investigation")
unreal.log("=" * 60)

elib = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

# --- 导入 FBX 到隔离区 ---
_plugin_python_dir = None
for p in sys.path:
    if "AssetCustoms" in p and p.endswith("Python"):
        _plugin_python_dir = p
        break
_content_dir = os.path.dirname(_plugin_python_dir)
_plugin_dir = os.path.dirname(_content_dir)
FBX_PATH = os.path.join(_plugin_dir, "Tests", "TestStaticMesh.fbx")

ISO_PATH = "/Game/_diag_mat_test"

# 清理旧测试
if elib.does_directory_exist(ISO_PATH):
    elib.delete_directory(ISO_PATH)

unreal.log(f"[DIAG-MAT] Importing FBX: {FBX_PATH}")
unreal.log(f"[DIAG-MAT] Isolation: {ISO_PATH}")

task = unreal.AssetImportTask()
task.set_editor_property("filename", FBX_PATH)
task.set_editor_property("destination_path", ISO_PATH)
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
unreal.log(f"[DIAG-MAT] Imported {len(imported_list)} assets:")
for a in imported_list:
    unreal.log(f"  {a}")

# --- 列出所有隔离区资产 ---
all_assets = list(elib.list_assets(ISO_PATH, recursive=True))
unreal.log(f"\n[DIAG-MAT] All assets in isolation ({len(all_assets)}):")

materials = []
textures = []
meshes = []

for asset_path in all_assets:
    clean = asset_path.split(".")[0] if "." in asset_path else asset_path
    obj = elib.load_asset(clean)
    type_name = type(obj).__name__ if obj else "None"
    unreal.log(f"  {clean} -> {type_name}")
    
    if isinstance(obj, unreal.MaterialInstanceConstant):
        materials.append(("MIC", clean, obj))
    elif isinstance(obj, unreal.Material):
        materials.append(("Material", clean, obj))
    elif isinstance(obj, unreal.Texture2D):
        textures.append((clean, obj))
    elif isinstance(obj, unreal.StaticMesh):
        meshes.append((clean, obj))

# --- 分析每个材质 ---
for mat_type, mat_path, mat_obj in materials:
    unreal.log(f"\n{'='*40}")
    unreal.log(f"[DIAG-MAT] Analyzing material: {mat_path}")
    unreal.log(f"[DIAG-MAT] Type: {mat_type}")
    
    if mat_type == "MIC":
        # 路径 A: MaterialInstanceConstant
        unreal.log("[DIAG-MAT] --- MIC: texture_parameter_values ---")
        try:
            tex_params = mat_obj.get_editor_property("texture_parameter_values")
            unreal.log(f"  Count: {len(tex_params)}")
            for tp in tex_params:
                info = tp.get_editor_property("parameter_info")
                param_name = str(info.get_editor_property("name"))
                tex = tp.get_editor_property("parameter_value")
                tex_path = tex.get_path_name() if tex else "None"
                tex_name = tex.get_name() if tex else "None"
                unreal.log(f"  Param: '{param_name}' -> Texture: {tex_name} ({tex_path})")
        except Exception as e:
            unreal.log_error(f"  Failed: {e}")
            traceback.print_exc()
        
        # get_texture_parameter_names
        unreal.log("[DIAG-MAT] --- get_texture_parameter_names ---")
        try:
            names = mel.get_texture_parameter_names(mat_obj)
            unreal.log(f"  Names: {list(names)}")
            for n in names:
                tex = mel.get_material_instance_texture_parameter_value(mat_obj, n)
                tex_info = f"{tex.get_name()} ({tex.get_path_name()})" if tex else "None"
                unreal.log(f"  '{n}' -> {tex_info}")
        except Exception as e:
            unreal.log_error(f"  Failed: {e}")
            traceback.print_exc()
            
        # 查看父材质
        unreal.log("[DIAG-MAT] --- Parent Material ---")
        try:
            parent = mat_obj.get_editor_property("parent")
            if parent:
                unreal.log(f"  Parent: {parent.get_name()} ({parent.get_path_name()})")
                unreal.log(f"  Parent type: {type(parent).__name__}")
            else:
                unreal.log("  No parent")
        except Exception as e:
            unreal.log_error(f"  Failed: {e}")

    elif mat_type == "Material":
        # 路径 B: 普通 Material
        unreal.log("[DIAG-MAT] --- Material: get_used_textures ---")
        try:
            used_tex = mel.get_used_textures(mat_obj)
            unreal.log(f"  Used textures ({len(used_tex)}):")
            for t in used_tex:
                unreal.log(f"    {t.get_name()} ({t.get_path_name()})")
        except Exception as e:
            unreal.log_error(f"  Failed: {e}")
            
        unreal.log("[DIAG-MAT] --- get_texture_parameter_names ---")
        try:
            names = mel.get_texture_parameter_names(mat_obj)
            unreal.log(f"  Names: {list(names)}")
        except Exception as e:
            unreal.log_error(f"  Failed: {e}")
        
        unreal.log("[DIAG-MAT] --- get_material_property_input_node ---")
        props_to_check = [
            ("MP_BASE_COLOR", unreal.MaterialProperty.MP_BASE_COLOR),
            ("MP_NORMAL", unreal.MaterialProperty.MP_NORMAL),
            ("MP_METALLIC", unreal.MaterialProperty.MP_METALLIC),
            ("MP_ROUGHNESS", unreal.MaterialProperty.MP_ROUGHNESS),
            ("MP_AMBIENT_OCCLUSION", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
            ("MP_EMISSIVE_COLOR", unreal.MaterialProperty.MP_EMISSIVE_COLOR),
            ("MP_SPECULAR", unreal.MaterialProperty.MP_SPECULAR),
            ("MP_OPACITY", unreal.MaterialProperty.MP_OPACITY),
        ]
        for prop_name, prop_enum in props_to_check:
            try:
                node = mel.get_material_property_input_node(mat_obj, prop_enum)
                if node:
                    node_type = type(node).__name__
                    unreal.log(f"  {prop_name}: {node_type}")
                    # 尝试读取 texture 属性
                    if hasattr(node, 'get_editor_property'):
                        try:
                            tex = node.get_editor_property("texture")
                            if tex:
                                unreal.log(f"    -> Texture: {tex.get_name()} ({tex.get_path_name()})")
                        except:
                            pass
                else:
                    unreal.log(f"  {prop_name}: (not connected)")
            except Exception as e:
                unreal.log(f"  {prop_name}: ERROR - {e}")

# --- 分析贴图 ---
unreal.log(f"\n[DIAG-MAT] Textures in isolation ({len(textures)}):")
for tex_path, tex_obj in textures:
    srgb = tex_obj.get_editor_property("srgb")
    unreal.log(f"  {tex_path} (sRGB={srgb})")

# --- 清理 ---
unreal.log(f"\n[DIAG-MAT] Cleaning up...")
elib.delete_directory(ISO_PATH)
unreal.log("[DIAG-MAT] Done.")
unreal.log("=" * 60)
