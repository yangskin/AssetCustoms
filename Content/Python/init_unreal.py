"""AssetCustoms 插件入口脚本。

职责：
1. 将 vendor_libs/ 注入 sys.path（第三方依赖统一存放处）
2. 定义运行时 CONFIG
3. 导入 UI 注册器和 Actions
4. 自动注册 Content Browser 工具栏下拉菜单

第三方依赖（如 PIL）由 deploy.ps1 安装到 Content/Python/vendor_libs/，
本脚本在最早期将该子目录加入 sys.path，保证后续 import 能找到依赖。

业务逻辑见 unreal_integration/actions.py
UI 注册逻辑见 unreal_integration/ui.py
"""
import sys as _sys
import os as _os

_vendor_libs = _os.path.join(_os.path.dirname(__file__), "vendor_libs")
if _os.path.isdir(_vendor_libs) and _vendor_libs not in _sys.path:
    _sys.path.insert(0, _vendor_libs)

import unreal

from unreal_integration.ui import AssetCustomsUI
from unreal_integration.actions import AssetCustomsActions

# 可选：在 Unreal 环境中暴露常用入口
try:
    from core.textures.layer_merge import BlendMode  # noqa: F401
    from core.textures.channel_pack import pack_channels  # noqa: F401
    from unreal_integration import (  # noqa: F401
        merge_textures_in_unreal,
        load_project_config,
    )
except Exception:
    pass

# ===== 运行时 CONFIG =====
CONFIG = {
    "module_alias": "asset_customs",
    "singleton_attr": "ASSET_CUSTOMS_UI",
    "section": "AssetCustoms",
    "asset_menu_path": "ContentBrowser.AssetContextMenu",
    "toolbar_menu_path": "ContentBrowser.Toolbar",
    "dropdown_from_configs": True,
    "dropdown_menu_name": "AssetCustoms.Presets",
    "dropdown_label": "AssetCustoms",
    "dropdown_tooltip": "AssetCustoms presets from Content/Config/AssetCustoms",
    "entries": {},
    "auto_register": True,
}

# ===== 自动注册 =====
if CONFIG.get("auto_register", False):
    try:
        import sys as _sys

        _alias = CONFIG.get("module_alias") or "asset_customs"
        _sys.modules[_alias] = _sys.modules.get(__name__)

        ASSET_CUSTOMS_UI = AssetCustomsUI(CONFIG, AssetCustomsActions)
        ASSET_CUSTOMS_UI.register_all()
        try:
            setattr(unreal, CONFIG.get("singleton_attr") or "ASSET_CUSTOMS_UI", ASSET_CUSTOMS_UI)
        except Exception:
            pass
    except Exception as e:
        unreal.log_error(f"[AssetCustoms] Initialization failed: {e}")
