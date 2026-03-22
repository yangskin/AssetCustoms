"""AssetCustoms E2E 原生嵌入贴图管线测试。

测试内容：FBX 内含贴图 → UE 自动提取 → 删除自动材质 → 重命名贴图 → 创建 MI → 链接。
使用 Tests/TestStaticMesh.fbx（复制到空目录模拟无外部贴图场景）。

执行方式：通过 remote-execute.py 远程执行。
"""
import unreal
import sys
import os
import traceback
import tempfile
import shutil

# ============================================================
# Phase 0: 路径初始化
# ============================================================
unreal.log("=" * 60)
unreal.log("[E2E-NATIVE] Native Embedded Texture Pipeline Test")
unreal.log("=" * 60)

_plugin_python_dir = None
for p in sys.path:
    if "AssetCustoms" in p and p.endswith("Python"):
        _plugin_python_dir = p
        break

if _plugin_python_dir is None:
    unreal.log_error("[E2E-NATIVE] AssetCustoms Content/Python not found in sys.path")
    raise RuntimeError("Plugin Python path not found")

_content_dir = os.path.dirname(_plugin_python_dir)
_plugin_dir = os.path.dirname(_content_dir)

TESTS_DIR = os.path.join(_plugin_dir, "Tests")
CONFIG_DIR = os.path.join(_content_dir, "Config", "AssetCustoms")
FBX_PATH = os.path.join(TESTS_DIR, "TestStaticMesh.fbx")
PROP_CONFIG = os.path.join(CONFIG_DIR, "Prop.jsonc")

MASTER_MAT_FULL = "/Game/MyProject/Materials/Masters/MM_Prop_PBR.MM_Prop_PBR"
MASTER_MAT_DIR = "/Game/MyProject/Materials/Masters"
MASTER_MAT_NAME = "MM_Prop_PBR"

# 关键：模拟"无外部贴图"场景
EMPTY_DROP_DIR = tempfile.mkdtemp(prefix="native_emb_test_")
FBX_IN_EMPTY = os.path.join(EMPTY_DROP_DIR, "TestStaticMesh.fbx")
shutil.copy2(FBX_PATH, FBX_IN_EMPTY)

unreal.log(f"[E2E-NATIVE] FBX:         {FBX_PATH}")
unreal.log(f"[E2E-NATIVE] FBX (empty): {FBX_IN_EMPTY}")
unreal.log(f"[E2E-NATIVE] Config:      {PROP_CONFIG}")

# ============================================================
# Phase 1: 前置条件检查
# ============================================================
unreal.log("[E2E-NATIVE] Phase 1: Checking prerequisites...")
assert os.path.isfile(FBX_IN_EMPTY), f"FBX not found: {FBX_IN_EMPTY}"
assert os.path.isfile(PROP_CONFIG), f"Config not found: {PROP_CONFIG}"

_tex_in_empty = [f for f in os.listdir(EMPTY_DROP_DIR) if f.lower().endswith((".png", ".tga", ".jpg"))]
unreal.log(f"[E2E-NATIVE] Texture files in drop dir: {_tex_in_empty} (should be empty)")
assert len(_tex_in_empty) == 0, "Drop dir should have no texture files"

# ============================================================
# Phase 2: 加载配置
# ============================================================
unreal.log("[E2E-NATIVE] Phase 2: Loading config...")
from core.config.loader import load_config
config = load_config(PROP_CONFIG)
unreal.log(f"[E2E-NATIVE] Config loaded: {len(config.texture_output_definitions)} outputs")

# ============================================================
# Phase 3: 确保母材质存在
# ============================================================
unreal.log("[E2E-NATIVE] Phase 3: Ensuring master material...")
elib = unreal.EditorAssetLibrary

_mat_existed = elib.does_asset_exist(MASTER_MAT_FULL)
if not _mat_existed:
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialFactoryNew()
    mat = asset_tools.create_asset(MASTER_MAT_NAME, MASTER_MAT_DIR, unreal.Material, factory)
    if mat:
        elib.save_asset(f"{MASTER_MAT_DIR}/{MASTER_MAT_NAME}")
        unreal.log("[E2E-NATIVE] Created master material")
else:
    unreal.log("[E2E-NATIVE] Master material already exists")

# ============================================================
# Phase 4: 执行导入管道（原生嵌入贴图路径）
# ============================================================
unreal.log("[E2E-NATIVE] Phase 4: Running import pipeline (native embedded path)...")
unreal.log("-" * 40)

try:
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
    unreal.log_error(f"[E2E-NATIVE] FATAL: Pipeline threw exception: {e}")
    traceback.print_exc()
    raise

# ============================================================
# Phase 5: 结果报告
# ============================================================
unreal.log("-" * 40)
unreal.log("[E2E-NATIVE] Phase 5: Results Report")
unreal.log(f"[E2E-NATIVE] Pipeline phase: {result.phase}")
unreal.log(f"[E2E-NATIVE] Pipeline success: {result.success}")
unreal.log(f"[E2E-NATIVE] Isolation path: {result.isolation_path}")

if result.check_result:
    cr = result.check_result
    unreal.log(f"[E2E-NATIVE] Check status: {cr.status.value}")
    unreal.log(f"[E2E-NATIVE] StaticMesh: {cr.static_mesh}")
    if cr.match_result:
        unreal.log(f"[E2E-NATIVE] Slot mapping: {dict(cr.match_result.mapping)}")

if result.names:
    n = result.names
    unreal.log(f"[E2E-NATIVE] Target path: {n.target_path}")
    unreal.log(f"[E2E-NATIVE] SM: {n.static_mesh}")
    unreal.log(f"[E2E-NATIVE] MI: {n.material_instance}")

if result.standardize_result:
    sr = result.standardize_result
    unreal.log(f"[E2E-NATIVE] Textures processed: {len(sr.textures)}")
    for pt in sr.textures:
        unreal.log(f"[E2E-NATIVE]   {pt.output_name} ({pt.suffix}) -> {pt.file_path}")
        unreal.log(f"[E2E-NATIVE]     param={pt.material_parameter}, srgb={pt.srgb}")

if result.errors:
    for err in result.errors:
        unreal.log_error(f"[E2E-NATIVE] Error: {err}")

# ============================================================
# Phase 6: 验证最终资产
# ============================================================
unreal.log("[E2E-NATIVE] Phase 6: Verifying assets...")
if result.success and result.names:
    target = result.names.target_path
    # 可能因版本策略使用了不同路径
    # 尝试列出资产
    try:
        assets = list(elib.list_assets(target, recursive=True))
        unreal.log(f"[E2E-NATIVE] Assets at {target}: {len(assets)}")
        for a in assets:
            unreal.log(f"[E2E-NATIVE]   {a}")
    except Exception as e:
        unreal.log_warning(f"[E2E-NATIVE] Cannot list: {e}")

    # 验证隔离区已清理
    iso = result.isolation_path
    if iso and elib.does_directory_exist(iso):
        unreal.log_warning(f"[E2E-NATIVE] WARN: Isolation area not cleaned: {iso}")
    else:
        unreal.log(f"[E2E-NATIVE] OK: Isolation area cleaned")

# ============================================================
# Phase 7: 清理测试资产
# ============================================================
unreal.log("[E2E-NATIVE] Phase 7: Cleanup...")

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
            unreal.log(f"[E2E-NATIVE] Cleaned: {cp}")
    except Exception as e:
        unreal.log_warning(f"[E2E-NATIVE] Cleanup failed: {cp}: {e}")

shutil.rmtree(EMPTY_DROP_DIR, ignore_errors=True)

# ============================================================
# Summary
# ============================================================
unreal.log("=" * 60)
if result.success:
    unreal.log("[E2E-NATIVE] *** TEST PASSED *** Native embedded pipeline completed!")
elif result.phase == "check":
    unreal.log_warning("[E2E-NATIVE] *** TEST PARTIAL *** Stopped at check phase")
else:
    unreal.log_error(f"[E2E-NATIVE] *** TEST FAILED *** at phase: {result.phase}")
    if result.errors:
        unreal.log_error(f"[E2E-NATIVE] Errors: {result.errors}")
unreal.log("=" * 60)
