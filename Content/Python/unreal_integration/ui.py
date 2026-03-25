"""AssetCustoms UI 注册器：负责 ToolMenus 菜单/工具栏条目的注册与管理。

从 init_unreal.py 拆分而来。依赖 unreal 模块，仅在 UE 编辑器环境中可用。
"""
import unreal


class AssetCustomsUI:
    """负责注册/卸载本插件的菜单与工具栏项。

    CONFIG 字段说明见 init_unreal.py 顶部文档。
    """

    def __init__(self, config: dict, actions_class: type | None = None) -> None:
        self.cfg = config
        self.menus = unreal.ToolMenus.get()
        self._actions_cls = actions_class
        self._actions = actions_class(config) if actions_class else None

    # --- 内部工具 ---
    def _build_ui_call_with_args(self, method: str, args: list[str] | None = None) -> str:
        """构造调用 UI 单例方法并传参的命令串。"""
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
        """构造可持久的回调调用字符串。"""
        import re as _re
        ui_singleton = self.cfg.get("singleton_attr") or "ASSET_CUSTOMS_UI"
        unreal_ui_attr = ui_singleton
        if ":" not in callback_spec:
            method = callback_spec.strip()
            if not _re.match(r"^[A-Za-z0-9_\.]+$", method):
                return "import unreal; unreal.log_error('Invalid method name')"
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
        mod, func = callback_spec.split(":", 1)
        mod = mod.strip(); func = func.strip()
        if not _re.match(r"^[A-Za-z0-9_\.]+$", mod) or not _re.match(r"^[A-Za-z0-9_\.]+$", func):
            return "import unreal; unreal.log_error('Invalid callback spec')"
        return (
            "import importlib as _il; _m=_il.import_module('" + mod + "'); "
            "getattr(_m, '" + func + "')()"
        )

    def _scan_config_presets(self) -> list[dict]:
        """扫描配置根目录下的 *.jsonc，返回 [{name,label,path}]。"""
        try:
            import os
            items: list[dict] = []

            try:
                _here = os.path.abspath(__file__)
                # ui.py -> unreal_integration/ -> Python/ -> Content/
                _plugin_content = os.path.dirname(os.path.dirname(os.path.dirname(_here)))
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

            try:
                content_dir = unreal.Paths.project_content_dir()
                cfg_dir = os.path.join(content_dir, "Config", "AssetCustoms")
                if os.path.isdir(cfg_dir):
                    for fn in sorted(os.listdir(cfg_dir)):
                        if fn.lower().endswith(".jsonc"):
                            name = os.path.splitext(fn)[0]
                            path = os.path.join(cfg_dir, fn)
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

        submenu_name = self.cfg.get("dropdown_menu_name") or "AssetCustoms.Presets"
        submenu_label = self.cfg.get("dropdown_label") or "AssetCustoms"
        submenu_tip = self.cfg.get("dropdown_tooltip") or "AssetCustoms Presets"
        try:
            menu.add_section(section, section)
        except Exception:
            pass
        try:
            menu.remove_menu(submenu_name)
        except Exception:
            pass

        try:
            sub_menu = menu.add_sub_menu(section, section, submenu_name, submenu_label, submenu_tip)
        except Exception:
            sub_menu = None
        if not sub_menu:
            try:
                sub_menu = self.menus.find_menu(submenu_name)
            except Exception:
                sub_menu = None
        if not sub_menu:
            sub_menu = self.menus.extend_menu(submenu_name)

        presets = self._scan_config_presets()
        if not presets:
            placeholder = self.make_py_entry(
                entry_name=f"{section}.NoPreset",
                label="\u26a0 \u914d\u7f6e\u7f3a\u5931 (Config Missing)",
                tooltip="\u672a\u627e\u5230\u914d\u7f6e\u6587\u4ef6\u3002\u8bf7\u5c06 .jsonc \u653e\u5165 Content/Config/AssetCustoms/\n"
                        "No preset configs found. Place .jsonc files under Content/Config/AssetCustoms/",
                python="import unreal; unreal.log_error('[AssetCustoms] \u914d\u7f6e\u7f3a\u5931: \u672a\u5728 Content/Config/AssetCustoms/ \u627e\u5230 .jsonc \u6587\u4ef6\u3002\u8bf7\u653e\u7f6e\u914d\u7f6e\u540e\u91cd\u542f\u7f16\u8f91\u5668\u3002')",
                is_toolbar=False,
                icon={"style_set": "EditorStyle", "style_name": "Icons.Error"},
            )
            try:
                sub_menu.add_menu_entry(section, placeholder)
            except Exception:
                pass
            unreal.log_warning("[AssetCustoms] NFR4: \u672a\u53d1\u73b0\u914d\u7f6e\u6587\u4ef6\uff0c\u4e0b\u62c9\u83dc\u5355\u5df2\u7981\u7528\u3002\u8bf7\u5c06 .jsonc \u653e\u5165 Content/Config/AssetCustoms/")
            return

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

        # Config Editor 入口——放在下拉菜单第一项（使用 FIRST 插入位置）
        ce_cmd = self._build_python_command("on_open_config_editor")
        ce_entry = self.make_py_entry(
            entry_name=f"{section}.OpenConfigEditor",
            label="\u2699 Config Editor",
            tooltip="Open graphical config editor for AssetCustoms presets",
            python=ce_cmd,
            is_toolbar=False,
            icon={"style_set": "EditorStyle", "style_name": "Icons.Settings"},
        )
        try:
            sub_menu.add_menu_entry(section, ce_entry)
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
        """在指定路径添加条目，若同名则先移除。"""
        menu = self.menus.extend_menu(menu_path)
        try:
            menu.remove_entry(self.cfg["section"], entry.name)
        except Exception:
            pass
        menu.add_menu_entry(self.cfg["section"], entry)

    def register_entry(self, e: dict) -> None:
        """注册单个条目。"""
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

    def _register_asset_context_menu(self) -> None:
        """在 Content Browser 资产右键菜单注册 'Send' 子菜单。"""
        asset_menu_path = self.cfg.get("asset_menu_path") or "ContentBrowser.AssetContextMenu"
        menu = self.menus.find_menu(asset_menu_path)
        if not menu:
            menu = self.menus.extend_menu(asset_menu_path)

        section = self.cfg.get("section") or "AssetCustoms"
        send_menu_name = f"{section}.Send"

        try:
            send_menu = menu.add_sub_menu(
                menu.get_name(), "GetAssetActions", send_menu_name, "Send", ""
            )
        except Exception:
            send_menu = self.menus.extend_menu(send_menu_name)

        if not send_menu:
            return

        ps_cmd = self._build_python_command("on_send_to_photoshop")
        ps_entry = self.make_py_entry(
            entry_name=f"{section}.SendToPhotoshop",
            label="Send to Photoshop",
            tooltip="在 Photoshop 中打开选中的贴图",
            python=ps_cmd,
            is_toolbar=False,
            icon={"style_set": "EditorStyle", "style_name": "ContentBrowser.AssetActions"},
        )
        try:
            send_menu.add_menu_entry("Send", ps_entry)
        except Exception:
            pass

        sp_cmd = self._build_python_command("on_send_to_substance_painter")
        sp_entry = self.make_py_entry(
            entry_name=f"{section}.SendToSubstancePainter",
            label="Send to Substance Painter",
            tooltip="发送选中的 StaticMesh 到 Substance Painter",
            python=sp_cmd,
            is_toolbar=False,
            icon={"style_set": "EditorStyle", "style_name": "ContentBrowser.AssetActions"},
        )
        try:
            send_menu.add_menu_entry("Send", sp_entry)
        except Exception:
            pass

        # --- Config Profile 子菜单 ---
        profile_menu_name = f"{section}.ConfigProfile"
        try:
            profile_menu = menu.add_sub_menu(
                menu.get_name(), "GetAssetActions", profile_menu_name, "Config Profile", ""
            )
        except Exception:
            profile_menu = self.menus.extend_menu(profile_menu_name)

        if profile_menu:
            profile_section = "ConfigProfile"
            try:
                profile_menu.add_section(profile_section, profile_section)
            except Exception:
                pass
            # View Profile
            view_cmd = self._build_python_command("on_view_config_profile")
            view_entry = self.make_py_entry(
                entry_name=f"{section}.ViewConfigProfile",
                label="View Profile",
                tooltip="查看选中资产的 Config Profile 标签",
                python=view_cmd,
                is_toolbar=False,
                icon={"style_set": "EditorStyle", "style_name": "Icons.Info"},
            )
            try:
                profile_menu.add_menu_entry(profile_section, view_entry)
            except Exception:
                pass

            # Set Profile — 直接平铺到 Config Profile 菜单（避免三级嵌套）
            presets = self._scan_config_presets()
            for p in presets:
                set_cmd = self._build_ui_call_with_args("on_set_config_profile", [p["name"]])
                set_entry = self.make_py_entry(
                    entry_name=f"{section}.SetProfile.{p['name']}",
                    label=f"Set: {p['label']}",
                    tooltip=f"将选中资产的 Config Profile 设为 {p['name']}",
                    python=set_cmd,
                    is_toolbar=False,
                    icon={"style_set": "EditorStyle", "style_name": "ClassIcon.StaticMesh"},
                )
                try:
                    profile_menu.add_menu_entry(profile_section, set_entry)
                except Exception:
                    pass

            # Clear Profile
            clear_cmd = self._build_python_command("on_clear_config_profile")
            clear_entry = self.make_py_entry(
                entry_name=f"{section}.ClearConfigProfile",
                label="Clear Profile",
                tooltip="清除选中资产的 Config Profile 标签",
                python=clear_cmd,
                is_toolbar=False,
                icon={"style_set": "EditorStyle", "style_name": "Icons.Delete"},
            )
            try:
                profile_menu.add_menu_entry(profile_section, clear_entry)
            except Exception:
                pass

    def register_all(self) -> None:
        """一次性注册并刷新 UI。"""
        if self.cfg.get("dropdown_from_configs", False):
            self._register_toolbar_dropdown_from_configs()
        self._register_asset_context_menu()
        for _key, e in (self.cfg.get("entries") or {}).items():
            self.register_entry(e)
        self.menus.refresh_all_widgets()
