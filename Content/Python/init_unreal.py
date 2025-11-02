import unreal


class AssetCustomsUI:
    """负责注册/卸载本插件的菜单与工具栏项。

        CONFIG 字段说明（dict）：
        - module_alias (str, 默认 "asset_customs")：
            - 为当前 Python 模块设置一个稳定别名，避免 Unreal 环境下多个同名文件（如 init_unreal.py）产生冲突。
            - 回调执行优先通过此别名导入模块进行查找。

        - singleton_attr (str, 默认 "ASSET_CUSTOMS_UI")：
            - 模块级 UI 单例变量名。初始化后会在本模块与 unreal 模块上各存一份，
                以保证点击菜单时能稳定拿到同一个实例（避免 __main__ 或热重载导致的回调丢失）。

        - section (str, 默认 "AssetCustoms")：
            - 在 ToolMenus 中使用的分组名（同一菜单路径下用于归类）。

        - asset_menu_path (str, 默认 "ContentBrowser.AssetContextMenu")：
            - 资产右键菜单路径。

        - toolbar_menu_path (str, 默认 "ContentBrowser.Toolbar")：
            - Content Browser 顶部工具栏路径。

        - entries (dict[str, EntryConfig])：
            - 要注册的所有菜单/按钮项。键名随意，仅用于本配置表内区分；每个值是一条 EntryConfig：
                EntryConfig 结构：
                - name (str, 必填)：此条目的唯一名称（ToolMenus 条目的 Name）。
                - label (str, 可选)：在 UI 上显示的文本；默认等于 name。
                - tooltip (str, 可选)：悬停提示；默认空串。
                - icon (dict, 可选)：按钮/菜单的图标描述，示例：
                        {"style_set": "EditorStyle", "style_name": "Icons.Help"}
                    注意：不同版本/皮肤下图标名可能不同，内部做了双重回退，设置失败会静默忽略。
                - callback (str, 可选)：回调规范。有两种写法：
                        1) "on_xxx"（不含冒号）：表示调用 Actions 实例中的同名方法（推荐）。
                        2) "some.module:callable"：显式模块路径 + 可调用对象（兼容旧用法）。
                    当 callback 缺失且提供了 python 字段时，会直接执行 python 中的命令串。
                - python (str, 可选)：直接执行的一段 Python 命令串（若提供，将优先于 callback 被使用）。
                - is_toolbar (bool, 默认 False)：是否注册为工具栏按钮；否则是普通菜单项。
                - menu_path (str, 可选)：覆盖级菜单路径；不填时按照 is_toolbar 在
                    toolbar_menu_path/asset_menu_path 二选一。

            - 常见用法示例（仅示意）：
                entries = {
                        "toolbar_create_pbr": {
                                "name": "AssetCustoms.Toolbar.CreatePBRMaterial",
                                "label": "PBR Material",
                                "tooltip": "Create a standard PBR Material at current folder",
                                "icon": {"style_set": "EditorStyle", "style_name": "ClassIcon.Material"},
                                "callback": "on_create_pbr_material",
                                "is_toolbar": True,
                                "menu_path": "ContentBrowser.Toolbar",
                        },
                        "context_hello": {
                                "name": "AssetCustoms.HelloWorld",
                                "label": "Hello World",
                                "tooltip": "Print 'hello world' to the Output Log",
                                "icon": {"style_set": "EditorStyle", "style_name": "Icons.Help"},
                                "callback": "on_hello_world",
                                "menu_path": "ContentBrowser.AssetContextMenu",
                        },
                }

        - pbr_defaults (dict, 可选)：创建标准 PBR 材质时使用的默认参数：
                {
                    "base_color": (r, g, b),   # 0.0~1.0，默认 (0.8, 0.8, 0.8)
                    "roughness": 0.5,          # float
                    "metallic": 0.0            # float
                }

        - auto_register (bool, 默认 False)：
            - True 时在模块加载后自动注册 entries 并刷新 UI。

        重要行为说明：
        - 回调解析：当 entry.callback 不含冒号时，会通过 UI 单例的 call_action 转到
            Actions 实例的方法；若单例缺失，会尽力按 module_alias 导入模块并临时构建。
        - 图标兼容：先尝试构造 ToolMenuEntryIcon 对象；失败则回退到 set_icon(style_set, style_name)。
        - 重复注册：同名条目会先 remove 再 add，便于热重载。
        - 仅支持 UE 5.5 的 Material 接线签名：connect_material_property(expr, "", MP_*)。
        - 资产创建落点：示例 Actions 会遵循当前 Content Browser 选中的目录；若为左侧树上的
            “/All/…” 路径会自动规范化到 “/Game/…”；并仅允许 /Game 与 /Engine 两个常见根。

        调用范例（Quick Start）：
        1) 手动注册（不启用 auto_register）：
            ASSET_CUSTOMS_UI = AssetCustomsUI(CONFIG, AssetCustomsActions)
            ASSET_CUSTOMS_UI.register_all()
            # 可选：也挂到 unreal 模块，点击时优先从这里拿，避免模块名问题
            try:
                setattr(unreal, CONFIG.get("singleton_attr") or "ASSET_CUSTOMS_UI", ASSET_CUSTOMS_UI)
            except Exception:
                pass

        2) 自动注册（推荐，需 CONFIG["auto_register"] = True）：
            if CONFIG.get("auto_register", False):
                try:
                    # 先为当前模块注册一个稳定别名，避免与工程内其他 init_unreal.py 冲突
                    import sys as _sys
                    _alias = CONFIG.get("module_alias") or "asset_customs"
                    _sys.modules[_alias] = _sys.modules.get(__name__)

                    # 创建并保存在模块级，供按钮点击时持久引用
                    ASSET_CUSTOMS_UI = AssetCustomsUI(CONFIG, AssetCustomsActions)
                    ASSET_CUSTOMS_UI.register_all()
                    # 也挂到 unreal 模块，点击时优先从这里拿，避免模块名问题
                    try:
                        setattr(unreal, CONFIG.get("singleton_attr") or "ASSET_CUSTOMS_UI", ASSET_CUSTOMS_UI)
                    except Exception:
                        pass
                # 初始化完成（静默）
                except Exception as e:
                    unreal.log_error(f"[AssetCustoms] Initialization failed: {e}")
    """

    def __init__(self, config: dict, actions_class: type | None = None) -> None:
        """传入外部配置 CONFIG（详见本类文档字符串中的“CONFIG 字段说明”）。"""
        self.cfg = config
        self.menus = unreal.ToolMenus.get()
        self._actions_cls = actions_class
        self._actions = actions_class(config) if actions_class else None

    # --- 内部工具 ---
    def _build_python_command(self, callback_spec: str) -> str:
        """构造可持久的回调调用字符串。
        规则：
        - 不包含冒号":"：认为是 AssetCustomsUI 单例实例的方法名，经由 UI.call_action(method) 调用。
        - 包含冒号：按 "some.module:callable" 直接调用模块级可调用（兼容旧用法）。
        """
        import re as _re
        ui_singleton = self.cfg.get("singleton_attr") or "ASSET_CUSTOMS_UI"
        unreal_ui_attr = ui_singleton
        if ":" not in callback_spec:
            method = callback_spec.strip()
            if not _re.match(r"^[A-Za-z0-9_\.]+$", method):
                return "import unreal; unreal.log_error('Invalid method name')"
            # 首选从 unreal 模块上拿到全局 UI 单例，避免模块名/重载导致的丢失
            # 如未找到，再尝试导入模块重建；最后兜底直接实例化 Actions 调用
            mod_alias = (self.cfg.get("module_alias") or (__name__ if __name__ != "__main__" else "init_unreal")).strip()
            return (
                "import importlib as _il, unreal as _unreal\n"
                f"_ui=getattr(_unreal,'{unreal_ui_attr}', None)\n"
                "if (_ui is None) or (not hasattr(_ui,'call_action')):\n"
                f"    try:\n        _m=_il.import_module('{mod_alias}')\n        if not hasattr(_m,'CONFIG'):\n            setattr(_m,'CONFIG',{{}})\n        if hasattr(_m,'AssetCustomsUI'):\n            setattr(_m,'{ui_singleton}', _m.AssetCustomsUI(_m.CONFIG, getattr(_m,'AssetCustomsActions', None)))\n            _ui=getattr(_m,'{ui_singleton}', None)\n            if _ui is not None:\n                setattr(_unreal,'{unreal_ui_attr}', _ui)\n    except Exception:\n        pass\n"
                f"if _ui and hasattr(_ui,'call_action'):\n    _ui.call_action('{method}')\n"
                "else:\n"
                f"    try:\n        _m=_il.import_module('{mod_alias}')\n        _act = getattr(_m,'AssetCustomsActions', None)\n        if _act is not None:\n            _inst = _act(getattr(_m,'CONFIG', {{}}))\n            if hasattr(_inst,'{method}'):\n                getattr(_inst,'{method}')()\n            else:\n                _unreal.log_error('[AssetCustoms] Action not found: {method}')\n        else:\n            _unreal.log_error('[AssetCustoms] No Actions class available')\n    except Exception as _ex:\n        _unreal.log_error('[AssetCustoms] Call failed: '+str(_ex))\n"
            )
        # 显式模块:可调用 路径
        mod, func = callback_spec.split(":", 1)
        mod = mod.strip(); func = func.strip()
        if not _re.match(r"^[A-Za-z0-9_\.]+$", mod) or not _re.match(r"^[A-Za-z0-9_\.]+$", func):
            return "import unreal; unreal.log_error('Invalid callback spec')"
        return (
            "import importlib as _il; _m=_il.import_module('" + mod + "'); "
            "getattr(_m, '" + func + "')()"
        )

    @staticmethod
    def make_py_entry(entry_name: str, label: str, tooltip: str, python: str, *, is_toolbar: bool = False, icon: dict | None = None) -> unreal.ToolMenuEntry:
        """构造一个执行 Python 命令的菜单/工具栏项。"""
        entry_type = unreal.MultiBlockType.TOOL_BAR_BUTTON if is_toolbar else unreal.MultiBlockType.MENU_ENTRY
        entry = unreal.ToolMenuEntry(
            name=entry_name,
            type=entry_type,
            insert_position=unreal.ToolMenuInsert("", unreal.ToolMenuInsertType.FIRST),
        )
        entry.set_label(label)
        entry.set_tool_tip(tooltip)
        entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "Python", python)
        # 尝试应用图标（不同版本 API 可能不同，做双重回退）
        if icon:
            try:
                icon_obj = unreal.ToolMenuEntryIcon(
                    style_set_name=icon.get("style_set", "EditorStyle"),
                    style_name=icon.get("style_name", "Icons.Help"),
                )
                entry.set_icon(icon_obj)
            except Exception:
                try:
                    entry.set_icon(icon.get("style_set", "EditorStyle"), icon.get("style_name", "Icons.Help"))
                except Exception:
                    pass
        return entry

    def add_or_replace(self, menu_path: str, entry: unreal.ToolMenuEntry) -> None:
        """在指定路径添加条目，若同名则先移除（适配热重载）。"""
        menu = self.menus.extend_menu(menu_path)
        try:
            menu.remove_entry(self.cfg["section"], entry.name)
        except Exception:
            pass
        menu.add_menu_entry(self.cfg["section"], entry)

    # --- 对外方法 ---
    def register_entry(self, e: dict) -> None:
        """注册单个条目，读取 e 配置创建菜单/按钮。"""
        if not e or "name" not in e:
            return
        python_cmd = e.get("python") or self._build_python_command(e.get("callback", ""))
        is_toolbar = bool(e.get("is_toolbar", False))
        menu_path = e.get("menu_path") or (self.cfg.get("toolbar_menu_path") if is_toolbar else self.cfg.get("asset_menu_path"))
        entry = self.make_py_entry(
            entry_name=e["name"],
            label=e.get("label", e["name"]),
            tooltip=e.get("tooltip", ""),
            python=python_cmd,
            is_toolbar=is_toolbar,
            icon=e.get("icon"),
        )
        self.add_or_replace(menu_path, entry)

    def call_action(self, method_name: str) -> None:
        """由按钮回调调用：转发到 actions 实例的方法。"""
        if not self._actions and self._actions_cls:
            try:
                self._actions = self._actions_cls(self.cfg)
            except Exception as ex:
                unreal.log_error(f"[AssetCustoms] Failed to create actions: {ex}")
                return
        target = getattr(self._actions, method_name, None) if self._actions else None
        if callable(target):
            try:
                target()
            except Exception as ex:
                unreal.log_error(f"[AssetCustoms] Action '{method_name}' failed: {ex}")
        else:
            unreal.log_error(f"[AssetCustoms] Action '{method_name}' not found or not callable")

    # 工具类不包含业务回调，回调移至独立的 Actions 类

    def register_all(self) -> None:
        """一次性注册并刷新 UI。"""
        for _key, e in (self.cfg.get("entries") or {}).items():
            self.register_entry(e)
        self.menus.refresh_all_widgets()


# 可选：在 Unreal 环境中暴露常用入口，便于按钮或命令行调用
try:
    # 纯 Python 核心（无 Unreal 依赖）
    from core.textures.layer_merge import BlendMode  # noqa: F401
    # Unreal 适配层
    from unreal_integration import (  # noqa: F401
        merge_textures_in_unreal,
        load_project_config,
    )
except Exception:
    # 在非 Unreal 或部分依赖缺失时保持加载不报错
    pass

    def unregister_all(self) -> None:
        """可选：卸载所有已注册条目（便于调试/热重载）。"""
        # 根据 entries 反注册
        for _key, e in (self.cfg.get("entries") or {}).items():
            name = e.get("name")
            if not name:
                continue
            is_toolbar = bool(e.get("is_toolbar", False))
            menu_path = e.get("menu_path") or (self.cfg.get("toolbar_menu_path") if is_toolbar else self.cfg.get("asset_menu_path"))
            menu = self.menus.extend_menu(menu_path)
            try:
                menu.remove_entry(self.cfg["section"], name)
            except Exception:
                pass
        self.menus.refresh_all_widgets()
