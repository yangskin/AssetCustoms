"""使用测试模型执行完整导入管道（不清理结果）。

导入 Tests/TestStaticMesh.fbx + 配套贴图 → Content Browser 可查看结果。
执行：remote-execute.py --file <this_file>
"""
import unreal
import sys
import os
import traceback
import importlib

# ============================================================
# 路径初始化
# ============================================================
unreal.log("=" * 60)
unreal.log("[IMPORT] Test Model Import (keep results)")
unreal.log("=" * 60)

_plugin_python_dir = None
for p in sys.path:
    if "AssetCustoms" in p and p.endswith("Python"):
        _plugin_python_dir = p
        break

if _plugin_python_dir is None:
    raise RuntimeError("AssetCustoms Content/Python not found in sys.path")

_content_dir = os.path.dirname(_plugin_python_dir)
_plugin_dir = os.path.dirname(_content_dir)

TESTS_DIR = os.path.join(_plugin_dir, "Tests")
CONFIG_DIR = os.path.join(_content_dir, "Config", "AssetCustoms")
FBX_PATH = os.path.join(TESTS_DIR, "TestStaticMesh.fbx")
PROP_CONFIG = os.path.join(CONFIG_DIR, "Prop.jsonc")

MASTER_MAT_DIR = "/Game/MyProject/Materials/Masters"
MASTER_MAT_NAME = "MM_Prop_PBR"
MASTER_MAT_FULL = f"{MASTER_MAT_DIR}/{MASTER_MAT_NAME}.{MASTER_MAT_NAME}"

unreal.log(f"[IMPORT] FBX:    {FBX_PATH}")
unreal.log(f"[IMPORT] Config: {PROP_CONFIG}")

# ============================================================
# 前置条件
# ============================================================
assert os.path.isfile(FBX_PATH), f"FBX not found: {FBX_PATH}"
assert os.path.isfile(PROP_CONFIG), f"Config not found: {PROP_CONFIG}"

_tex_files = [f for f in os.listdir(TESTS_DIR) if f.lower().endswith((".png", ".tga", ".jpg"))]
unreal.log(f"[IMPORT] Texture files found: {len(_tex_files)} — {_tex_files}")

# ============================================================
# 加载配置
# ============================================================
unreal.log("[IMPORT] Loading config...")
from core.config.loader import load_config
config = load_config(PROP_CONFIG)
unreal.log(f"[IMPORT] Config loaded: v{config.config_version}, {len(config.texture_output_definitions)} outputs")

# ============================================================
# 确保母材质存在
# ============================================================
elib = unreal.EditorAssetLibrary
if not elib.does_asset_exist(MASTER_MAT_FULL):
    unreal.log("[IMPORT] Creating master material...")
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialFactoryNew()
    mat = asset_tools.create_asset(MASTER_MAT_NAME, MASTER_MAT_DIR, unreal.Material, factory)
    if mat:
        elib.save_asset(f"{MASTER_MAT_DIR}/{MASTER_MAT_NAME}")
        unreal.log("[IMPORT] Master material created")
    else:
        unreal.log_error("[IMPORT] Failed to create master material")
else:
    unreal.log("[IMPORT] Master material already exists")

# ============================================================
# 执行导入管道
# ============================================================
unreal.log("[IMPORT] Running import pipeline...")
unreal.log("-" * 40)

# 强制重载以获取最新代码
import unreal_integration.import_pipeline as _ip_mod
importlib.reload(_ip_mod)
from unreal_integration.import_pipeline import run_import_pipeline

result = run_import_pipeline(
    fbx_path=FBX_PATH,
    config=config,
    category="Prop",
    current_path="/Game",
)

# ============================================================
# 结果报告
# ============================================================
unreal.log("-" * 40)
unreal.log(f"[IMPORT] Phase: {result.phase}")
unreal.log(f"[IMPORT] Success: {result.success}")

if result.check_result and result.check_result.match_result:
    mapping = dict(result.check_result.match_result.mapping)
    unreal.log(f"[IMPORT] Texture mapping: {mapping}")

if result.names:
    n = result.names
    unreal.log(f"[IMPORT] Target path:       {n.target_path}")
    unreal.log(f"[IMPORT] StaticMesh:        {n.static_mesh}")
    unreal.log(f"[IMPORT] MaterialInstance:   {n.material_instance}")

if result.standardize_result:
    for pt in result.standardize_result.textures:
        unreal.log(f"[IMPORT]   {pt.output_name} ({pt.suffix}) -> {pt.file_path}")

if result.errors:
    for err in result.errors:
        unreal.log_error(f"[IMPORT] Error: {err}")

# 列出最终资产
if result.success and result.names:
    target = result.names.target_path
    assets = list(elib.list_assets(target, recursive=True))
    unreal.log(f"[IMPORT] Created assets at {target}:")
    for a in assets:
        unreal.log(f"[IMPORT]   {a}")

unreal.log("=" * 60)
if result.success:
    unreal.log("[IMPORT] *** DONE *** Assets kept in Content Browser — browse to target path to view.")
else:
    unreal.log_error(f"[IMPORT] *** FAILED *** at phase: {result.phase}")
unreal.log("=" * 60)
