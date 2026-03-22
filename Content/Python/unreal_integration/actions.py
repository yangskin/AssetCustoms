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
        """基于指定预设执行 FBX 选择，并触发完整导入管道。"""
        unreal.log(f"[AssetCustoms] Preset selected: {preset_path}")
        paths = self._open_fbx_file_dialog()
        if not paths:
            return
        fbx_path = paths[0]
        unreal.log(f"[AssetCustoms] FBX selected: {fbx_path}")

        try:
            from unreal_integration.import_context import build_import_context
            from unreal_integration.import_pipeline import run_import_pipeline
            import os

            ctx = build_import_context(fbx_path=fbx_path, profile_path=preset_path)
            category = os.path.splitext(os.path.basename(preset_path))[0]
            unreal.log(
                "[AssetCustoms] ImportContext built: "
                f"content_path={ctx.content_path}, profile_path={ctx.profile_path}, "
                f"config_version={ctx.profile.config_version}, "
                f"outputs={len(ctx.profile.texture_output_definitions)}"
            )

            # 执行完整导入管道（FR2 → FR3 → FR5）
            result = run_import_pipeline(
                fbx_path=fbx_path,
                config=ctx.profile,
                category=category,
                current_path=ctx.content_path,
            )

            if result.success:
                unreal.log(f"[AssetCustoms] 标准化完成: {result.names.target_path if result.names else 'N/A'}")
            elif result.check_result and not result.check_result.passed:
                # 检查失败 → 需要分诊 UI（FR4，待实现）
                reasons = "; ".join(f.reason for f in result.check_result.failures)
                unreal.log_warning(f"[AssetCustoms] 检查未通过: {reasons}")
                unreal.log_warning(f"[AssetCustoms] 资产保留在隔离区: {result.isolation_path}")
            else:
                for err in result.errors:
                    unreal.log_error(f"[AssetCustoms] {err}")

        except Exception as ex:
            unreal.log_error(f"[AssetCustoms] Import pipeline failed: {ex}")
