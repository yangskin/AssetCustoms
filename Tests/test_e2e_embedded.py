"""AssetCustoms E2E 嵌入贴图测试 — FBX 内含贴图，无外部纹理文件。

测试流程：FBX 导入（嵌入贴图提取） → 检查链 → 标准化 完整流程。
使用 Tests/TestStaticMesh.fbx（内含 1 张 BaseColor 嵌入贴图）。

执行方式：通过 remote-execute.py 远程执行。
"""
import unreal
import sys
import os
import traceback

# ============================================================
# Phase 0: 路径初始化
# ============================================================
unreal.log("=" * 60)
unreal.log("[E2E-EMB] Embedded Texture Pipeline Test")
unreal.log("=" * 60)

_plugin_python_dir = None
for p in sys.path:
    if "AssetCustoms" in p and p.endswith("Python"):
        _plugin_python_dir = p
        break

if _plugin_python_dir is None:
    unreal.log_error("[E2E-EMB] AssetCustoms Content/Python not found in sys.path")
    raise RuntimeError("Plugin Python path not found")

_content_dir = os.path.dirname(_plugin_python_dir)
_plugin_dir = os.path.dirname(_content_dir)

TESTS_DIR = os.path.join(_plugin_dir, "Tests")
CONFIG_DIR = os.path.join(_content_dir, "Config", "AssetCustoms")
FBX_PATH = os.path.join(TESTS_DIR, "TestStaticMesh.fbx")
PROP_CONFIG = os.path.join(CONFIG_DIR, "Prop.jsonc")

# 关键：模拟"无外部贴图"场景 — 使用一个空的临时目录作为 FBX 的"所在目录"
# 这样 discover_texture_files 找不到任何磁盘贴图，触发嵌入贴图回退逻辑
import tempfile
EMPTY_DROP_DIR = tempfile.mkdtemp(prefix="empty_drop_")

# 将 FBX 复制到空目录（管道通过 fbx_path 所在目录来搜索贴图）
import shutil
FBX_IN_EMPTY = os.path.join(EMPTY_DROP_DIR, "TestStaticMesh.fbx")
shutil.copy2(FBX_PATH, FBX_IN_EMPTY)

MASTER_MAT_FULL = "/Game/MyProject/Materials/Masters/MM_Prop_PBR.MM_Prop_PBR"
MASTER_MAT_DIR = "/Game/MyProject/Materials/Masters"
MASTER_MAT_NAME = "MM_Prop_PBR"

unreal.log(f"[E2E-EMB] FBX:         {FBX_PATH}")
unreal.log(f"[E2E-EMB] FBX (empty): {FBX_IN_EMPTY}")
unreal.log(f"[E2E-EMB] Config:      {PROP_CONFIG}")
unreal.log(f"[E2E-EMB] Empty dir:   {EMPTY_DROP_DIR}")

# ============================================================
# Phase 1: 前置条件检查
# ============================================================
unreal.log("[E2E-EMB] Phase 1: Checking prerequisites...")
_ok = True

if not os.path.isfile(FBX_IN_EMPTY):
    unreal.log_error(f"[E2E-EMB] FAIL: FBX not found: {FBX_IN_EMPTY}")
    _ok = False
else:
    unreal.log(f"[E2E-EMB] OK: FBX exists ({os.path.getsize(FBX_IN_EMPTY)} bytes)")

if not os.path.isfile(PROP_CONFIG):
    unreal.log_error(f"[E2E-EMB] FAIL: Config not found: {PROP_CONFIG}")
    _ok = False

# 验证空目录中无贴图文件
_tex_in_empty = [f for f in os.listdir(EMPTY_DROP_DIR) if f.lower().endswith((".png", ".tga", ".jpg"))]
unreal.log(f"[E2E-EMB] Texture files in drop dir: {_tex_in_empty} (should be empty)")
assert len(_tex_in_empty) == 0, "Drop dir should have no texture files for this test"

if not _ok:
    raise RuntimeError("[E2E-EMB] Prerequisites check failed")

# ============================================================
# Phase 2: 加载配置
# ============================================================
unreal.log("[E2E-EMB] Phase 2: Loading Prop.jsonc config...")
try:
    from core.config.loader import load_config
    config = load_config(PROP_CONFIG)
    unreal.log(f"[E2E-EMB] OK: Config loaded, {len(config.texture_output_definitions)} output defs")
except Exception as e:
    unreal.log_error(f"[E2E-EMB] FAIL: Config load error: {e}")
    traceback.print_exc()
    raise

# ============================================================
# Phase 3: 创建测试用母材质
# ============================================================
unreal.log("[E2E-EMB] Phase 3: Ensuring master material exists...")
elib = unreal.EditorAssetLibrary

_mat_existed = elib.does_asset_exist(MASTER_MAT_FULL)
if _mat_existed:
    unreal.log("[E2E-EMB] OK: Master material already exists")
else:
    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialFactoryNew()
        mat = asset_tools.create_asset(MASTER_MAT_NAME, MASTER_MAT_DIR, unreal.Material, factory)
        if mat:
            elib.save_asset(f"{MASTER_MAT_DIR}/{MASTER_MAT_NAME}")
            unreal.log(f"[E2E-EMB] OK: Created master material")
    except Exception as e:
        unreal.log_error(f"[E2E-EMB] FAIL: Cannot create master material: {e}")

# ============================================================
# Phase 4: 执行导入管道（使用空目录中的 FBX → 触发嵌入贴图回退）
# ============================================================
unreal.log("[E2E-EMB] Phase 4: Running import pipeline (embedded texture path)...")
unreal.log("-" * 40)

try:
    # 强制重载修改过的模块（UE session 可能缓存了旧版本）
    import importlib
    import unreal_integration.import_pipeline as _ip_mod
    importlib.reload(_ip_mod)
    from unreal_integration.import_pipeline import run_import_pipeline

    result = run_import_pipeline(
        fbx_path=FBX_IN_EMPTY,
        config=config,
        category="Prop",
        current_path="/Game",
    )
except Exception as e:
    unreal.log_error(f"[E2E-EMB] FATAL: Pipeline threw exception: {e}")
    traceback.print_exc()
    raise

# ============================================================
# Phase 5: 结果报告
# ============================================================
unreal.log("-" * 40)
unreal.log("[E2E-EMB] Phase 5: Results Report")
unreal.log(f"[E2E-EMB] Pipeline phase reached: {result.phase}")
unreal.log(f"[E2E-EMB] Pipeline success: {result.success}")
unreal.log(f"[E2E-EMB] Isolation path: {result.isolation_path}")

if result.check_result:
    cr = result.check_result
    unreal.log(f"[E2E-EMB] Check status: {cr.status.value}")
    unreal.log(f"[E2E-EMB] StaticMesh: {cr.static_mesh}")
    if cr.match_result:
        unreal.log(f"[E2E-EMB] Texture mapping: {dict(cr.match_result.mapping)}")
        unreal.log(f"[E2E-EMB] Orphans: {cr.match_result.orphans}")
        unreal.log(f"[E2E-EMB] Unmapped slots: {cr.match_result.unmapped_slots}")
    for f in cr.failures:
        unreal.log_warning(f"[E2E-EMB] Check FAILED: [{f.check_name}] {f.reason}")
        if f.details:
            unreal.log_warning(f"[E2E-EMB]   Details: {f.details}")
else:
    unreal.log_warning("[E2E-EMB] No check result")

if result.names:
    n = result.names
    unreal.log(f"[E2E-EMB] Resolved names:")
    unreal.log(f"[E2E-EMB]   base_name:         {n.base_name}")
    unreal.log(f"[E2E-EMB]   static_mesh:       {n.static_mesh}")
    unreal.log(f"[E2E-EMB]   material_instance: {n.material_instance}")
    unreal.log(f"[E2E-EMB]   target_path:       {n.target_path}")

if result.standardize_result:
    sr = result.standardize_result
    unreal.log(f"[E2E-EMB] Standardize success: {sr.success}")
    for pt in sr.textures:
        unreal.log(f"[E2E-EMB]   Output: {pt.output_name} ({pt.suffix}) -> {pt.file_path}")
    for err in sr.errors:
        unreal.log_error(f"[E2E-EMB]   Standardize error: {err}")

if result.errors:
    unreal.log_error(f"[E2E-EMB] Pipeline errors ({len(result.errors)}):")
    for err in result.errors:
        unreal.log_error(f"[E2E-EMB]   {err}")

# ============================================================
# Phase 6: 验证最终资产
# ============================================================
unreal.log("[E2E-EMB] Phase 6: Verifying created assets...")
if result.success and result.names:
    target = result.names.target_path
    try:
        assets = list(elib.list_assets(target, recursive=True))
        unreal.log(f"[E2E-EMB] Assets at {target}: {assets}")
    except Exception as e:
        unreal.log_warning(f"[E2E-EMB] Cannot list assets at {target}: {e}")

# ============================================================
# Phase 7: 清理
# ============================================================
unreal.log("[E2E-EMB] Phase 7: Cleanup...")

_cleanup_paths = []
if result.success and result.names:
    _cleanup_paths.append(result.names.target_path)

_iso = result.isolation_path
if _iso and elib.does_directory_exist(_iso):
    _cleanup_paths.append(_iso)

if not _mat_existed:
    _cleanup_paths.append(MASTER_MAT_DIR)

for cp in _cleanup_paths:
    try:
        if elib.does_directory_exist(cp):
            elib.delete_directory(cp)
            unreal.log(f"[E2E-EMB] Cleaned up: {cp}")
        elif elib.does_asset_exist(cp):
            elib.delete_asset(cp)
            unreal.log(f"[E2E-EMB] Cleaned up asset: {cp}")
    except Exception as e:
        unreal.log_warning(f"[E2E-EMB] Cleanup failed for {cp}: {e}")

# 清理磁盘临时目录
shutil.rmtree(EMPTY_DROP_DIR, ignore_errors=True)

# ============================================================
# Summary
# ============================================================
unreal.log("=" * 60)
if result.success:
    unreal.log("[E2E-EMB] *** TEST PASSED *** Embedded texture pipeline completed!")
elif result.phase == "check" and result.check_result and not result.check_result.passed:
    unreal.log_warning("[E2E-EMB] *** TEST PARTIAL *** Import OK, check chain reported failures")
    unreal.log_warning(f"[E2E-EMB] Failures: {[f.reason for f in result.check_result.failures]}")
elif result.phase == "import":
    unreal.log_error("[E2E-EMB] *** TEST FAILED *** Failed at import phase")
else:
    unreal.log_warning(f"[E2E-EMB] *** TEST INCOMPLETE *** Stopped at phase: {result.phase}")
    unreal.log_warning(f"[E2E-EMB] Errors: {result.errors}")
unreal.log("=" * 60)
