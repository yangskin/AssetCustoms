"""AssetCustoms 插件入口脚本。

职责：
1. 定义运行时 CONFIG
2. 导入 UI 注册器和 Actions
3. 自动注册 Content Browser 工具栏下拉菜单

第三方依赖（如 PIL）由 deploy.ps1 直接安装到 Content/Python/，
UE 启动时自动将该目录加入 sys.path，无需额外路径注入。

业务逻辑见 unreal_integration/actions.py
UI 注册逻辑见 unreal_integration/ui.py
"""
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
