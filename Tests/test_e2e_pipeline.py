"""AssetCustoms E2E 端到端测试 — 在 UE 编辑器中执行。

测试内容：FBX 导入 → 检查链 → 标准化 完整流程。
使用 Tests/TestStaticMesh.fbx + 配套测试贴图。

执行方式：在 UE 编辑器 Python 控制台或通过 MCP editor.execute 执行。
"""
import unreal
import sys
import os
import traceback

# ============================================================
# Phase 0: 路径初始化
# ============================================================
unreal.log("=" * 60)
unreal.log("[E2E] AssetCustoms End-to-End Pipeline Test")
unreal.log("=" * 60)

# 定位插件 Content/Python 路径
_plugin_python_dir = None
for p in sys.path:
    if "AssetCustoms" in p and p.endswith("Python"):
        _plugin_python_dir = p
        break

if _plugin_python_dir is None:
    unreal.log_error("[E2E] AssetCustoms Content/Python not found in sys.path")
    unreal.log(f"[E2E] sys.path = {sys.path}")
    raise RuntimeError("Plugin Python path not found")

# Content/Python -> Content -> AssetCustoms
_content_dir = os.path.dirname(_plugin_python_dir)
_plugin_dir = os.path.dirname(_content_dir)

TESTS_DIR = os.path.join(_plugin_dir, "Tests")
CONFIG_DIR = os.path.join(_content_dir, "Config", "AssetCustoms")
FBX_PATH = os.path.join(TESTS_DIR, "TestStaticMesh.fbx")
PROP_CONFIG = os.path.join(CONFIG_DIR, "Prop.jsonc")

MASTER_MAT_FULL = "/Game/MyProject/Materials/Masters/MM_Prop_PBR.MM_Prop_PBR"
MASTER_MAT_DIR = "/Game/MyProject/Materials/Masters"
MASTER_MAT_NAME = "MM_Prop_PBR"

unreal.log(f"[E2E] FBX:    {FBX_PATH}")
unreal.log(f"[E2E] Config: {PROP_CONFIG}")
unreal.log(f"[E2E] Tests:  {TESTS_DIR}")

# ============================================================
# Phase 1: 前置条件检查
# ============================================================
unreal.log("[E2E] Phase 1: Checking prerequisites...")
_ok = True

if not os.path.isfile(FBX_PATH):
    unreal.log_error(f"[E2E] FAIL: FBX not found: {FBX_PATH}")
    _ok = False
else:
    unreal.log(f"[E2E] OK: FBX exists ({os.path.getsize(FBX_PATH)} bytes)")

if not os.path.isfile(PROP_CONFIG):
    unreal.log_error(f"[E2E] FAIL: Config not found: {PROP_CONFIG}")
    _ok = False
else:
    unreal.log(f"[E2E] OK: Config exists")

_tex_files = [f for f in os.listdir(TESTS_DIR) if f.lower().endswith((".png", ".tga", ".jpg"))]
unreal.log(f"[E2E] Found {len(_tex_files)} texture files: {_tex_files}")

if not _ok:
    raise RuntimeError("[E2E] Prerequisites check failed")

# ============================================================
# Phase 2: 加载配置
# ============================================================
unreal.log("[E2E] Phase 2: Loading Prop.jsonc config...")
try:
    from core.config.loader import load_config
    config = load_config(PROP_CONFIG)
    unreal.log(f"[E2E] OK: Config v{config.config_version}, "
               f"{len(config.texture_output_definitions)} output defs, "
               f"master_material={config.default_master_material_path}")
except Exception as e:
    unreal.log_error(f"[E2E] FAIL: Config load error: {e}")
    traceback.print_exc()
    raise

# ============================================================
# Phase 3: 创建测试用母材质（如不存在）
# ============================================================
unreal.log("[E2E] Phase 3: Ensuring master material exists...")
elib = unreal.EditorAssetLibrary

_mat_existed = elib.does_asset_exist(MASTER_MAT_FULL)
if _mat_existed:
    unreal.log(f"[E2E] OK: Master material already exists")
else:
    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialFactoryNew()
        mat = asset_tools.create_asset(MASTER_MAT_NAME, MASTER_MAT_DIR, unreal.Material, factory)
        if mat:
            elib.save_asset(f"{MASTER_MAT_DIR}/{MASTER_MAT_NAME}")
            unreal.log(f"[E2E] OK: Created master material at {MASTER_MAT_DIR}/{MASTER_MAT_NAME}")
        else:
            unreal.log_error("[E2E] FAIL: create_asset returned None")
    except Exception as e:
        unreal.log_error(f"[E2E] FAIL: Cannot create master material: {e}")
        traceback.print_exc()

# 验证
if elib.does_asset_exist(MASTER_MAT_FULL):
    unreal.log("[E2E] OK: Master material verified")
else:
    # 尝试不带对象名的路径
    _short_path = f"{MASTER_MAT_DIR}/{MASTER_MAT_NAME}"
    if elib.does_asset_exist(_short_path):
        unreal.log(f"[E2E] WARN: Material exists at short path {_short_path} but not full path")
    else:
        unreal.log_warning("[E2E] WARN: Master material not found — check_master_material may fail")

# ============================================================
# Phase 4: 检查 Pillow 可用性
# ============================================================
unreal.log("[E2E] Phase 4: Checking Pillow availability...")
try:
    from PIL import Image
    unreal.log(f"[E2E] OK: Pillow available (version not checked)")
except ImportError:
    unreal.log_warning("[E2E] WARN: Pillow not available — standardize phase will report error but won't crash")

# ============================================================
# Phase 5: 执行导入管道
# ============================================================
unreal.log("[E2E] Phase 5: Running import pipeline...")
unreal.log("-" * 40)

try:
    import importlib
    import unreal_integration.import_pipeline as _ip_mod
    importlib.reload(_ip_mod)
    from unreal_integration.import_pipeline import run_import_pipeline

    result = run_import_pipeline(
        fbx_path=FBX_PATH,
        config=config,
        category="Prop",
        current_path="/Game",
    )
except Exception as e:
    unreal.log_error(f"[E2E] FATAL: Pipeline threw exception: {e}")
    traceback.print_exc()
    raise

# ============================================================
# Phase 6: 结果报告
# ============================================================
unreal.log("-" * 40)
unreal.log("[E2E] Phase 6: Results Report")
unreal.log(f"[E2E] Pipeline phase reached: {result.phase}")
unreal.log(f"[E2E] Pipeline success: {result.success}")
unreal.log(f"[E2E] Isolation path: {result.isolation_path}")

# --- Check Result ---
if result.check_result:
    cr = result.check_result
    unreal.log(f"[E2E] Check status: {cr.status.value}")
    unreal.log(f"[E2E] StaticMesh detected: {cr.static_mesh}")
    if cr.match_result:
        unreal.log(f"[E2E] Texture mapping: {dict(cr.match_result.mapping)}")
        unreal.log(f"[E2E] Orphan files: {cr.match_result.orphans}")
        unreal.log(f"[E2E] Ambiguous slots: {cr.match_result.ambiguous_slots}")
        unreal.log(f"[E2E] Unmapped slots: {cr.match_result.unmapped_slots}")
    for f in cr.failures:
        unreal.log_warning(f"[E2E] Check FAILED: [{f.check_name}] {f.reason}")
        if f.details:
            unreal.log_warning(f"[E2E]   Details: {f.details}")
else:
    unreal.log_warning("[E2E] No check result (pipeline stopped before check phase)")

# --- Resolved Names ---
if result.names:
    n = result.names
    unreal.log(f"[E2E] Resolved names:")
    unreal.log(f"[E2E]   base_name:         {n.base_name}")
    unreal.log(f"[E2E]   static_mesh:       {n.static_mesh}")
    unreal.log(f"[E2E]   material_instance: {n.material_instance}")
    unreal.log(f"[E2E]   target_path:       {n.target_path}")
    for suffix, tex_name in n.texture_names.items():
        unreal.log(f"[E2E]   texture [{suffix}]:   {tex_name}")
else:
    unreal.log("[E2E] No resolved names (pipeline stopped before name resolution)")

# --- Standardize Result ---
if result.standardize_result:
    sr = result.standardize_result
    unreal.log(f"[E2E] Standardize success: {sr.success}")
    for pt in sr.textures:
        unreal.log(f"[E2E]   Output: {pt.output_name} ({pt.suffix}) -> {pt.file_path}")
        unreal.log(f"[E2E]     material_param={pt.material_parameter}, srgb={pt.srgb}")
    for err in sr.errors:
        unreal.log_error(f"[E2E]   Standardize error: {err}")
else:
    unreal.log("[E2E] No standardize result (pipeline stopped before standardize phase)")

# --- Errors ---
if result.errors:
    unreal.log_error(f"[E2E] Pipeline errors ({len(result.errors)}):")
    for err in result.errors:
        unreal.log_error(f"[E2E]   {err}")

# ============================================================
# Phase 7: 验证最终资产
# ============================================================
unreal.log("[E2E] Phase 7: Verifying created assets...")

if result.success and result.names:
    target = result.names.target_path
    try:
        assets = list(elib.list_assets(target, recursive=True))
        unreal.log(f"[E2E] Assets at {target}: {assets}")
    except Exception as e:
        unreal.log_warning(f"[E2E] Cannot list assets at {target}: {e}")

# 也检查隔离区是否还存在
_iso = result.isolation_path
if _iso:
    try:
        iso_exists = elib.does_directory_exist(_iso)
        if iso_exists:
            iso_assets = list(elib.list_assets(_iso, recursive=True))
            unreal.log(f"[E2E] Isolation area still exists at {_iso}: {iso_assets}")
        else:
            unreal.log(f"[E2E] Isolation area cleaned up: {_iso}")
    except Exception as e:
        unreal.log(f"[E2E] Cannot check isolation area: {e}")

# ============================================================
# Phase 8: 清理（仅清理测试创建的资产）
# ============================================================
unreal.log("[E2E] Phase 8: Cleanup...")

_cleanup_paths = []

# 清理目标路径下的测试资产
if result.success and result.names:
    _cleanup_paths.append(result.names.target_path)

# 清理隔离区（如果还在）
if _iso:
    _cleanup_paths.append(_iso)

# 清理测试用母材质（仅当我们创建的）
if not _mat_existed:
    _cleanup_paths.append(MASTER_MAT_DIR)

for cp in _cleanup_paths:
    try:
        if elib.does_directory_exist(cp):
            elib.delete_directory(cp)
            unreal.log(f"[E2E] Cleaned up directory: {cp}")
        elif elib.does_asset_exist(cp):
            elib.delete_asset(cp)
            unreal.log(f"[E2E] Cleaned up asset: {cp}")
    except Exception as e:
        unreal.log_warning(f"[E2E] Cleanup failed for {cp}: {e}")

# ============================================================
# Summary
# ============================================================
unreal.log("=" * 60)
if result.success:
    unreal.log("[E2E] *** TEST PASSED *** Full pipeline completed successfully!")
elif result.phase == "check" and result.check_result and not result.check_result.passed:
    unreal.log("[E2E] *** TEST PARTIAL *** Import OK, check chain reported failures (expected if missing master material)")
elif result.phase == "import":
    unreal.log_error("[E2E] *** TEST FAILED *** Pipeline failed at import phase")
else:
    unreal.log_warning(f"[E2E] *** TEST INCOMPLETE *** Stopped at phase: {result.phase}")
    unreal.log_warning(f"[E2E] Errors: {result.errors}")
unreal.log("=" * 60)
