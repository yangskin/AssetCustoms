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
    def _build_ui_call_with_args(self, method: str, args: list[str] | None = None) -> str:
        """构造调用 UI 单例方法并传参的命令串。
        优先从 unreal 模块拿单例；若不存在则尝试按 module_alias 导入并重建。
        """
        ui_singleton = self.cfg.get("singleton_attr") or "ASSET_CUSTOMS_UI"
        mod_alias = (self.cfg.get("module_alias") or (__name__ if __name__ != "__main__" else "init_unreal")).strip()
        args_src = ", ".join([repr(a) for a in (args or [])])
        return (
            "import importlib as _il, unreal as _unreal\n"
            f"_ui=getattr(_unreal,'{ui_singleton}', None)\n"
            "if (_ui is None) or (not hasattr(_ui,'call_action_with_args')):\n"
            f"    try:\n        _m=_il.import_module('{mod_alias}')\n        if not hasattr(_m,'CONFIG'):\n            setattr(_m,'CONFIG',{{}})\n        if hasattr(_m,'AssetCustomsUI'):\n            setattr(_m,'{ui_singleton}', _m.AssetCustomsUI(_m.CONFIG, getattr(_m,'AssetCustomsActions', None)))\n            _ui=getattr(_m,'{ui_singleton}', None)\n            if _ui is not None:\n                setattr(_unreal,'{ui_singleton}', _ui)\n    except Exception:\n        pass\n"
            f"if _ui and hasattr(_ui,'call_action_with_args'):\n    _ui.call_action_with_args('{method}'{(', ' + args_src) if args_src else ''})\n"
            "else:\n    _unreal.log_error('[AssetCustoms] UI singleton not available for calling with args')\n"
        )

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

    def _scan_config_presets(self) -> list[dict]:
        """扫描配置根目录下的 *.jsonc，返回 [{name,label,path}]。
        搜索顺序：插件 Content（相对当前脚本）、项目 Content（Paths.project_content_dir）。
        """
        try:
            import os
            items: list[dict] = []

            # 1) 插件 Content 根（通过当前文件路径回溯）
            try:
                _here = os.path.abspath(__file__)
                _plugin_content = os.path.dirname(os.path.dirname(_here))  # .../Content
                _cfg_dir = os.path.join(_plugin_content, "Config", "AssetCustoms")
                if os.path.isdir(_cfg_dir):
                    for fn in sorted(os.listdir(_cfg_dir)):
                        if fn.lower().endswith(".jsonc"):
                            name = os.path.splitext(fn)[0]
                            items.append({
                                "name": name,
                                "label": name,
                                "path": os.path.join(_cfg_dir, fn),
                            })
            except Exception:
                pass

            # 2) 项目 Content 根
            try:
                content_dir = unreal.Paths.project_content_dir()
                cfg_dir = os.path.join(content_dir, "Config", "AssetCustoms")
                if os.path.isdir(cfg_dir):
                    for fn in sorted(os.listdir(cfg_dir)):
                        if fn.lower().endswith(".jsonc"):
                            name = os.path.splitext(fn)[0]
                            path = os.path.join(cfg_dir, fn)
                            # 去重
                            if not any(os.path.normcase(x["path"]) == os.path.normcase(path) for x in items):
                                items.append({
                                    "name": name,
                                    "label": name,
                                    "path": path,
                                })
            except Exception:
                pass

            return items
        except Exception:
            return []

    def _register_toolbar_dropdown_from_configs(self) -> None:
        """在 Content Browser 工具栏注册一个下拉菜单，子项由配置文件 (*.jsonc) 动态生成。"""
        toolbar_path = self.cfg.get("toolbar_menu_path") or "ContentBrowser.Toolbar"
        section = self.cfg.get("section") or "AssetCustoms"
        menu = self.menus.extend_menu(toolbar_path)

        # 定义子菜单
        submenu_name = self.cfg.get("dropdown_menu_name") or "AssetCustoms.Presets"
        submenu_label = self.cfg.get("dropdown_label") or "AssetCustoms"
        submenu_tip = self.cfg.get("dropdown_tooltip") or "AssetCustoms Presets"
        # 确保节存在（在 Toolbar 下以节为分组）
        try:
            menu.add_section(section, section)
        except Exception:
            pass
        try:
            # 重复注册时，尝试先移除旧的同名子菜单（忽略失败）
            menu.remove_menu(submenu_name)
        except Exception:
            pass

        # 添加子菜单并获取其对象
        try:
            sub_menu = menu.add_sub_menu(section, section, submenu_name, submenu_label, submenu_tip)
        except Exception:
            # 某些版本返回 None，需要通过名称查找
            sub_menu = None
        if not sub_menu:
            try:
                sub_menu = self.menus.find_menu(submenu_name)
            except Exception:
                sub_menu = None
        if not sub_menu:
            # 兜底：直接扩展同名菜单
            sub_menu = self.menus.extend_menu(submenu_name)

        # 填充子菜单条目
        presets = self._scan_config_presets()
        if not presets:
            # 没有配置文件，放一个只读提示项
            placeholder = self.make_py_entry(
                entry_name=f"{section}.NoPreset",
                label="No Presets Found",
                tooltip="Put *.jsonc under Content/Config/AssetCustoms",
                python="import unreal; unreal.log_warning('[AssetCustoms] No presets found')",
                is_toolbar=False,
                icon={"style_set": "EditorStyle", "style_name": "Icons.Warning"},
            )
            try:
                sub_menu.add_menu_entry(section, placeholder)
            except Exception:
                pass
            return

        # 清理旧条目（若可用）
        try:
            # 无显式 API 清空子菜单，这里以覆盖式 add 方式（同名 remove 再 add）
            pass
        except Exception:
            pass

        for p in presets:
            py_cmd = self._build_ui_call_with_args("on_pick_fbx_with_preset", [p["path"]])
            entry = self.make_py_entry(
                entry_name=f"{section}.Preset.{p['name']}",
                label=p["label"],
                tooltip=p["path"],
                python=py_cmd,
                is_toolbar=False,
                icon={"style_set": "EditorStyle", "style_name": "ClassIcon.StaticMesh"},
            )
            try:
                sub_menu.add_menu_entry(section, entry)
            except Exception:
                pass

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

    def call_action_with_args(self, method_name: str, *args, **kwargs) -> None:
        """允许带参数的回调调用。"""
        if not self._actions and self._actions_cls:
            try:
                self._actions = self._actions_cls(self.cfg)
            except Exception as ex:
                unreal.log_error(f"[AssetCustoms] Failed to create actions: {ex}")
                return
        target = getattr(self._actions, method_name, None) if self._actions else None
        if callable(target):
            try:
                target(*args, **kwargs)
            except Exception as ex:
                unreal.log_error(f"[AssetCustoms] Action '{method_name}' failed: {ex}")
        else:
            unreal.log_error(f"[AssetCustoms] Action '{method_name}' not found or not callable")

    # 工具类不包含业务回调，回调移至独立的 Actions 类

    def register_all(self) -> None:
        """一次性注册并刷新 UI。"""
        # 优先：配置驱动的下拉菜单
        if self.cfg.get("dropdown_from_configs", False):
            self._register_toolbar_dropdown_from_configs()
        # 兼容：静态 entries 仍然可用
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


# ===== 最小 Actions 实现与工具栏按钮：Content Browser 上添加 “Import FBX…” 按钮 =====
class AssetCustomsActions:
    """存放按钮回调的业务方法。此类应尽量不依赖全局状态。"""

    def __init__(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or {}

    # ---- 工具方法 ----
    def _get_content_browser_path(self) -> str:
        """返回当前 Content Browser 路径，若无选择则返回 /Game。"""
        try:
            # UE 5.5+: BlueprintFunctionLibrary 不应实例化，直接调用类方法
            selected_path = unreal.EditorUtilityLibrary.get_current_content_browser_path()
            return selected_path or "/Game"
        except Exception:
            return "/Game"

    def _tk_open_files(self, title: str, filetypes: list[tuple[str, str]]) -> list[str]:
        """优先使用 tkinter 打开文件选择对话框（多选）。失败则返回空列表。

        示例 filetypes：[("FBX files", "*.fbx"), ("All files", "*.*")]
        """
        try:
            import tkinter as tk  # type: ignore
            from tkinter import filedialog  # type: ignore

            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口，仅展示对话框
            files = filedialog.askopenfilenames(title=title, filetypes=filetypes)
            try:
                root.destroy()
            except Exception:
                pass
            # askopenfilenames 可能返回元组或空字符串
            if not files:
                return []
            return [str(p) for p in (files if isinstance(files, (list, tuple)) else [files])]
        except Exception as ex:
            try:
                unreal.log_warning(f"[AssetCustoms] tkinter 对话框不可用，回退到 Editor 对话框。原因: {ex}")
            except Exception:
                pass
            return []

    def _open_fbx_file_dialog(self) -> list[str]:
        """使用 tkinter 打开仅 .fbx 的文件选择对话框，返回所选路径列表（可能为空）。"""
        tk_files = self._tk_open_files(
            title="Select FBX",
            filetypes=[("FBX files", "*.fbx"), ("All files", "*.*")],
        )
        if tk_files:
            return tk_files
        unreal.log_error("[AssetCustoms] 未选择文件或 tkinter 不可用，已取消操作。")
        return []

    # ---- 按钮回调 ----
    def on_pick_fbx(self) -> None:
        content_path = self._get_content_browser_path()
        unreal.log(f"[AssetCustoms] Current Content Browser Path: {content_path}")

        paths = self._open_fbx_file_dialog()
        if not paths:
            return
        # 仅取第一项；后续可扩展批量
        fbx_path = paths[0]
        unreal.log(f"[AssetCustoms] FBX selected: {fbx_path}")
        # TODO: 可在此触发后续导入流程（FR2），当前仅完成选择与日志显示

    def on_pick_fbx_with_preset(self, preset_path: str) -> None:
        """基于指定预设执行 FBX 选择（当前示例先记录预设路径）。"""
        unreal.log(f"[AssetCustoms] Preset selected: {preset_path}")
        # 选择 FBX
        paths = self._open_fbx_file_dialog()
        if not paths:
            return
        fbx_path = paths[0]
        unreal.log(f"[AssetCustoms] FBX selected: {fbx_path}")

        # 构建导入上下文（解析 JSONC 预设 + 采样 Content Browser 路径）
        try:
            from unreal_integration import build_import_context  # 延迟导入，便于非 Unreal 环境

            ctx = build_import_context(fbx_path=fbx_path, profile_path=preset_path)
            # 先记录关键信息；后续在 FR2/FR3 接入导入与检查链
            unreal.log(
                "[AssetCustoms] ImportContext built: "
                f"content_path={ctx.content_path}, profile_path={ctx.profile_path}, "
                f"merge_default={{mode:{ctx.profile.texture_merge.mode.name}, opacity:{ctx.profile.texture_merge.opacity}}}"
            )
        except Exception as ex:
            unreal.log_error(f"[AssetCustoms] Build ImportContext failed: {ex}")


# ===== 运行时 CONFIG：注册 Content Browser 工具栏按钮 =====
CONFIG = {
    "module_alias": "asset_customs",
    "singleton_attr": "ASSET_CUSTOMS_UI",
    "section": "AssetCustoms",
    "asset_menu_path": "ContentBrowser.AssetContextMenu",
    "toolbar_menu_path": "ContentBrowser.Toolbar",
    # 使用配置驱动的下拉菜单
    "dropdown_from_configs": True,
    "dropdown_menu_name": "AssetCustoms.Presets",
    "dropdown_label": "AssetCustoms",
    "dropdown_tooltip": "AssetCustoms presets from Content/Config/AssetCustoms",
    "entries": {},
    "auto_register": True,
}

# 自动注册（利用上面的示例流程）
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
        