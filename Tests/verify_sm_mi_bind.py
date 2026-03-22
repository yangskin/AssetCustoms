"""清理并重新导入测试模型，然后检查 SM→MI 绑定。"""
import unreal
import sys
import os
import importlib

elib = unreal.EditorAssetLibrary

TARGET = "/Game/Assets/Prop/TestStaticMesh"

# 清理旧资产
if elib.does_directory_exist(TARGET):
    assets = elib.list_assets(TARGET, recursive=True)
    for a in assets:
        elib.delete_asset(a.split(".")[0])
    elib.delete_directory(TARGET)
    unreal.log(f"[VERIFY] Cleaned {TARGET}")
else:
    unreal.log(f"[VERIFY] {TARGET} does not exist, skip clean")

# 重新导入
_plugin_python_dir = None
for p in sys.path:
    if "AssetCustoms" in p and p.endswith("Python"):
        _plugin_python_dir = p
        break

_content_dir = os.path.dirname(_plugin_python_dir)
_plugin_dir = os.path.dirname(_content_dir)
TESTS_DIR = os.path.join(_plugin_dir, "Tests")
CONFIG_DIR = os.path.join(_content_dir, "Config", "AssetCustoms")
FBX_PATH = os.path.join(TESTS_DIR, "TestStaticMesh.fbx")
PROP_CONFIG = os.path.join(CONFIG_DIR, "Prop.jsonc")

from core.config.loader import load_config
config = load_config(PROP_CONFIG)

import unreal_integration.import_pipeline as _ip_mod
importlib.reload(_ip_mod)
from unreal_integration.import_pipeline import run_import_pipeline

result = run_import_pipeline(fbx_path=FBX_PATH, config=config, category="Prop", current_path="/Game")

unreal.log(f"[VERIFY] Import success={result.success}, phase={result.phase}")

# 检查 SM→MI 绑定
SM_PATH = f"{TARGET}/SM_TestStaticMesh"
MI_PATH = f"{TARGET}/MI_TestStaticMesh"

sm = elib.load_asset(SM_PATH)
mi = elib.load_asset(MI_PATH)

if sm:
    materials = sm.get_editor_property("static_materials")
    if materials and len(materials) > 0:
        bound_mat = materials[0].get_editor_property("material_interface")
        if bound_mat:
            unreal.log(f"[VERIFY] ✅ SM slot[0] material = {bound_mat.get_path_name()}")
        else:
            unreal.log_error("[VERIFY] ❌ SM slot[0] material = None!")
    else:
        unreal.log_error("[VERIFY] ❌ SM has no material slots!")
else:
    unreal.log_error("[VERIFY] ❌ SM not found!")

if mi:
    parent = mi.get_editor_property("parent")
    unreal.log(f"[VERIFY] MI parent = {parent.get_path_name() if parent else 'None'}")

unreal.log("[VERIFY] Done")
