"""AssetCustoms 业务回调（Actions）：存放所有按钮触发的业务逻辑。

从 init_unreal.py 拆分而来。依赖 unreal 模块，仅在 UE 编辑器环境中可用。
"""
import unreal


class AssetCustomsActions:
    """存放按钮回调的业务方法。此类应尽量不依赖全局状态。"""

    def __init__(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or {}

    # ---- 工具方法 ----
    def _get_content_browser_path(self) -> str:
        """返回当前 Content Browser 路径，若无选择则返回 /Game。"""
        try:
            selected_path = unreal.EditorUtilityLibrary.get_current_content_browser_path()
            return selected_path or "/Game"
        except Exception:
            return "/Game"

    def _tk_open_files(self, title: str, filetypes: list[tuple[str, str]]) -> list[str]:
        """优先使用 tkinter 打开文件选择对话框（多选）。失败则返回空列表。"""
        try:
            import tkinter as tk  # type: ignore
            from tkinter import filedialog  # type: ignore

            root = tk.Tk()
            root.withdraw()
            files = filedialog.askopenfilenames(title=title, filetypes=filetypes)
            try:
                root.destroy()
            except Exception:
                pass
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
        """使用 tkinter 打开仅 .fbx 的文件选择对话框。"""
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
        fbx_path = paths[0]
        unreal.log(f"[AssetCustoms] FBX selected: {fbx_path}")

    def on_pick_fbx_with_preset(self, preset_path: str) -> None:
        """基于指定预设执行 FBX 选择，并触发完整导入管道。

        单文件走原始流程（含即时分诊），多文件走批处理（分诊排队）。
        """
        import os

        # NFR4: 配置文件存在性检查
        if not preset_path or not os.path.isfile(preset_path):
            unreal.log_error(
                f"[AssetCustoms] 配置文件不存在或路径无效: {preset_path}\n"
                "请确认 Content/Config/AssetCustoms/ 下有有效的 .jsonc 文件。"
            )
            return

        unreal.log(f"[AssetCustoms] Preset selected: {preset_path}")
        paths = self._open_fbx_file_dialog()
        if not paths:
            return

        try:
            from unreal_integration.import_context import build_import_context

            ctx = build_import_context(fbx_path=paths[0], profile_path=preset_path)
            category = os.path.splitext(os.path.basename(preset_path))[0]

            # 当 target_path_template 为空时，必须有有效内容浏览器目录
            if not ctx.profile.output.target_path_template:
                cp = ctx.content_path
                if not cp or cp == "/Game" or not cp.startswith("/Game/"):
                    unreal.log_error(
                        "[AssetCustoms] 目标路径模板为空，且未在内容浏览器中选择有效目录。\n"
                        "请先在内容浏览器中选择一个目标目录，再执行导入。"
                    )
                    try:
                        from unreal_qt import widget_manager as wm
                        wm.ensure_app()
                        from PySide6 import QtWidgets
                        QtWidgets.QMessageBox.warning(
                            None,
                            "AssetCustoms",
                            "目标路径模板为空，请先在内容浏览器中选中一个目录再导入。\n\n"
                            "Target path template is empty. Please select a folder "
                            "in Content Browser before importing.",
                        )
                    except Exception:
                        pass
                    return

            if len(paths) == 1:
                self._run_single_import(paths[0], ctx, category)
            else:
                self._run_batch_import(paths, ctx, category)
        except Exception as ex:
            unreal.log_error(f"[AssetCustoms] Import pipeline failed: {ex}")

    def _run_single_import(self, fbx_path: str, ctx, category: str) -> None:
        """单个 FBX 导入（原始流程，含即时分诊）。"""
        from unreal_integration.import_pipeline import run_import_pipeline

        unreal.log(f"[AssetCustoms] FBX selected: {fbx_path}")
        unreal.log(
            "[AssetCustoms] ImportContext built: "
            f"content_path={ctx.content_path}, profile_path={ctx.profile_path}, "
            f"config_version={ctx.profile.config_version}, "
            f"outputs={len(ctx.profile.processing.texture_definitions)}"
        )

        result = run_import_pipeline(
            fbx_path=fbx_path,
            config=ctx.profile,
            category=category,
            current_path=ctx.content_path,
        )

        if result.success:
            unreal.log(f"[AssetCustoms] 标准化完成: {result.names.target_path if result.names else 'N/A'}")
        elif result.check_result and not result.check_result.passed:
            reasons = "; ".join(f.reason for f in result.check_result.failures)
            unreal.log_warning(f"[AssetCustoms] 检查未通过: {reasons}")
            unreal.log_warning(f"[AssetCustoms] 资产保留在隔离区: {result.isolation_path}")
            self._show_triage_ui(result)
        else:
            for err in result.errors:
                unreal.log_error(f"[AssetCustoms] {err}")

    def _run_batch_import(self, fbx_paths: list, ctx, category: str) -> None:
        """批量 FBX 导入（M4）。"""
        from unreal_integration.import_pipeline import run_batch_import

        unreal.log(f"[AssetCustoms] 批处理开始: {len(fbx_paths)} 个文件")

        def on_progress(current: int, total: int, filename: str) -> None:
            unreal.log(f"[AssetCustoms] 批处理 [{current}/{total}]: {filename}")

        batch_result = run_batch_import(
            fbx_paths=fbx_paths,
            config=ctx.profile,
            category=category,
            current_path=ctx.content_path,
            on_progress=on_progress,
        )

        # 汇总日志
        unreal.log(f"[AssetCustoms] {batch_result.summary}")

        for item in batch_result.items:
            r = item.pipeline_result
            if r and r.success:
                unreal.log(
                    f"[AssetCustoms] ✔ {item.fbx_path} → "
                    f"{r.names.target_path if r.names else 'N/A'}"
                )
            elif r and r.errors:
                for err in r.errors:
                    unreal.log_error(f"[AssetCustoms] ✖ {item.fbx_path}: {err}")

        # 批处理后逐个弹出分诊 UI
        triage_items = [it for it in batch_result.items if it.needs_triage and it.pipeline_result]
        if triage_items:
            unreal.log_warning(
                f"[AssetCustoms] {len(triage_items)} 个文件需要分诊，将逐个弹出分诊窗口"
            )
            self._show_batch_triage(triage_items, 0)

    def _show_batch_triage(self, triage_items: list, index: int) -> None:
        """递归弹出批量分诊 UI：处理完当前项后自动弹出下一个。"""
        if index >= len(triage_items):
            unreal.log("[AssetCustoms] 批量分诊全部完成")
            return

        item = triage_items[index]
        result = item.pipeline_result
        remaining = len(triage_items) - index

        unreal.log(
            f"[AssetCustoms] 分诊 [{index + 1}/{len(triage_items)}]: "
            f"{item.fbx_path} (剩余 {remaining})"
        )

        # 包装 on_accept/on_cancel 以在完成后弹出下一项
        original_result = result

        def on_done():
            self._show_batch_triage(triage_items, index + 1)

        self._show_triage_ui(original_result, on_done_callback=on_done)

    # ---- FR4 分诊 UI ----
    def _show_triage_ui(self, pipeline_result, on_done_callback=None) -> None:
        """弹出分诊 UI 窗口，用户修正映射后继续执行 FR5。

        Args:
            pipeline_result: 管线失败结果。
            on_done_callback: 分诊完成/取消后的回调（用于批量分诊链式调用）。
        """
        try:
            import unreal_qt
            from core.pipeline.triage_ui import TriageWindow
            from unreal_integration.import_pipeline import resume_after_triage

            unreal_qt.setup()

            tc = pipeline_result.triage_context
            base_name = tc.base_name if tc else ""
            all_textures = tc.all_texture_paths if tc else []

            def on_accept(decision):
                unreal.log(f"[AssetCustoms] 分诊确认: base_name={decision.base_name}, "
                           f"mapping={len(decision.corrected_mapping)} slots")
                try:
                    resumed = resume_after_triage(
                        pipeline_result=pipeline_result,
                        corrected_mapping=decision.corrected_mapping,
                        corrected_base_name=decision.base_name,
                    )
                    if resumed.success:
                        unreal.log(f"[AssetCustoms] 分诊后标准化完成: "
                                   f"{resumed.names.target_path if resumed.names else 'N/A'}")
                    else:
                        for err in resumed.errors:
                            unreal.log_error(f"[AssetCustoms] {err}")
                except Exception as ex:
                    unreal.log_error(f"[AssetCustoms] 分诊后执行失败: {ex}")
                finally:
                    if on_done_callback:
                        on_done_callback()

            def on_cancel():
                unreal.log_warning(
                    f"[AssetCustoms] 分诊取消，资产保留在隔离区: {pipeline_result.isolation_path}")
                if on_done_callback:
                    on_done_callback()

            window = TriageWindow(
                check_result=pipeline_result.check_result,
                base_name=base_name,
                all_texture_paths=all_textures,
                on_accept=on_accept,
                on_cancel=on_cancel,
            )
            window.show()
            unreal_qt.wrap(window)
            unreal.log("[AssetCustoms] FR4 分诊 UI 已弹出")

        except Exception as ex:
            unreal.log_error(f"[AssetCustoms] 分诊 UI 打开失败: {ex}")
            unreal.log_warning(f"[AssetCustoms] 资产保留在隔离区: {pipeline_result.isolation_path}")

    # ---- 配置编辑器 ----
    def on_open_config_editor(self) -> None:
        """打开 JSONC 配置编辑器窗口。"""
        try:
            import os
            import unreal_qt
            from unreal_integration.config_editor import open_config_editor

            unreal_qt.setup()

            # 查找配置目录
            config_dir = None
            try:
                _here = os.path.abspath(__file__)
                _plugin_content = os.path.dirname(os.path.dirname(os.path.dirname(_here)))
                _cfg = os.path.join(_plugin_content, "Config", "AssetCustoms")
                if os.path.isdir(_cfg):
                    config_dir = _cfg
            except Exception:
                pass
            if not config_dir:
                try:
                    content_dir = unreal.Paths.project_content_dir()
                    _cfg = os.path.join(content_dir, "Config", "AssetCustoms")
                    if os.path.isdir(_cfg):
                        config_dir = _cfg
                except Exception:
                    pass

            if not config_dir:
                unreal.log_error("[AssetCustoms] 未找到配置目录 Content/Config/AssetCustoms/")
                return

            window = open_config_editor(config_dir=config_dir)
            unreal_qt.wrap(window)
            unreal.log("[AssetCustoms] 配置编辑器已打开")

        except Exception as ex:
            unreal.log_error(f"[AssetCustoms] 配置编辑器打开失败: {ex}")
