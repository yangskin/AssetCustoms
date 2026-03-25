"""unreal_integration 测试 conftest。

绕过 unreal_integration/__init__.py 的 UE 依赖，
直接将模块文件路径加入 sys.path 以允许在无 unreal 环境下测试纯逻辑模块。
"""
import sys
import os

# Content/Python
_python_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# 阻止 unreal_integration 作为包被自动导入（因为 __init__.py 依赖 unreal）
# 改为把 unreal_integration 目录加入 path 后直接 import 模块文件
_ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 将 Content/Python 加入 path（供 from unreal_integration.xxx 使用时需要 mock）
if _python_root not in sys.path:
    sys.path.insert(0, _python_root)

# Mock 掉 unreal 模块和依赖 unreal 的 __init__.py
# 这样 from unreal_integration.sp_remote import ... 可以正常工作
import types
if "unreal" not in sys.modules:
    sys.modules["unreal"] = types.ModuleType("unreal")

# Mock PIL 和 psd_tools（photoshop_bridge 依赖）
for mod_name in ("PIL", "PIL.Image", "psd_tools", "psd_tools.PSDImage"):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# 防止 pytest 收集上级目录中依赖 unreal 的模块
collect_ignore_glob = ["../__init__.py", "../ui.py", "../actions.py", "../photoshop_bridge.py",
                       "../texture_tools.py", "../settings.py", "../import_context.py",
                       "../import_pipeline.py", "../config_editor.py"]
