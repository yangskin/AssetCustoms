"""Photoshop 贴图编辑桥接模块。

提供从 UE Content Browser 右键发送贴图到 Photoshop 的功能，
并监控文件变化自动重新导入。

迁移自 Reference/send_tools.py，适配 AssetCustoms 插件架构。
依赖：PIL (Pillow), psd_tools (psd-tools)
"""
import os
import subprocess
from typing import List, Optional, Tuple

import unreal
from PIL import Image
from psd_tools import PSDImage

# 配置项
PHOTOSHOP_CUSTOM_PATH = ""  # 自定义 Photoshop 安装路径
PHOTOSHOP_DEFAULT_PATH = os.path.join(
    os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Adobe"
)


class TickTimer:
    """定时器基类，用于处理虚幻引擎的 tick 事件。"""

    def __init__(self, interval: float = 1.0):
        self._tick = unreal.register_slate_post_tick_callback(self._timer)
        self.interval = interval
        self._current_interval = 0.0

    def _timer(self, delta: float) -> None:
        self._current_interval += delta
        if self._current_interval < self.interval:
            return
        self._current_interval = 0.0

    def stop(self) -> None:
        if self._tick:
            unreal.unregister_slate_post_tick_callback(self._tick)


class IMonitorCallback:
    """监控器回调接口。"""

    def cleanup_all_temp_file(self) -> None:
        pass

    def stop_monitor(self, monitor: "TextureMonitor") -> None:
        pass


class TextureMonitor(TickTimer):
    """监控贴图文件变化并自动重新导入。

    继承自 TickTimer，每秒检测一次文件修改时间变化。
    Photoshop 进程退出后自动清理临时文件。
    """

    def __init__(
        self,
        texture_path: str,
        asset_path: str,
        callback: IMonitorCallback,
        process: subprocess.Popen,
    ):
        if not os.path.exists(texture_path):
            return

        self.texture_path = texture_path
        self.asset_path = asset_path
        self.callback = callback
        self.process = process
        self.last_modified = os.path.getmtime(texture_path)

        super().__init__(1.0)

    def _timer(self, delta: float) -> None:
        super()._timer(delta)
        if not os.path.exists(self.texture_path):
            return
        if self._should_cleanup():
            self._cleanup()
            return
        self._check_for_changes()

    def _should_cleanup(self) -> bool:
        return self.process.poll() is not None

    def _cleanup(self) -> None:
        self.callback.cleanup_all_temp_file()
        self.callback.stop_monitor(self)
        self.process.terminate()

    def _check_for_changes(self) -> None:
        current_modified = os.path.getmtime(self.texture_path)
        if current_modified == self.last_modified:
            return
        self.last_modified = current_modified
        self._reimport_texture()

    def _reimport_texture(self) -> None:
        if not unreal.EditorAssetLibrary.does_asset_exist(self.asset_path):
            return
        texture = unreal.EditorAssetLibrary.load_asset(self.asset_path)
        settings = self._store_texture_settings(texture)
        self._do_reimport()
        self._restore_texture_settings(texture, settings)

    def _store_texture_settings(self, texture) -> dict:
        return {
            "srgb": texture.get_editor_property("srgb"),
            "compression_settings": texture.get_editor_property("compression_settings"),
            "lod_group": texture.get_editor_property("lod_group"),
        }

    def _do_reimport(self) -> None:
        import_data = unreal.AutomatedAssetImportData()
        import_data.set_editor_property(
            "destination_path", os.path.dirname(self.asset_path)
        )
        import_data.set_editor_property("filenames", [self.texture_path])
        import_data.set_editor_property("replace_existing", True)
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        tools.import_assets_automated(import_data)

    def _restore_texture_settings(self, texture, settings: dict) -> None:
        for prop, value in settings.items():
            texture.set_editor_property(prop, value)


class PhotoshopBridge(IMonitorCallback):
    """处理与 Photoshop 的交互。

    功能流程：
    1. 导出选中的 Texture2D 为 TGA → 转换为 PSD
    2. 启动 Photoshop 打开 PSD 文件
    3. TextureMonitor 监控文件变化，自动重新导入
    4. Photoshop 关闭后自动清理临时文件
    """

    def __init__(self):
        self.asset_path = ""
        self.texture_monitors: List[TextureMonitor] = []

    def cleanup_all_temp_file(self) -> None:
        for monitor in self.texture_monitors:
            if os.path.exists(monitor.texture_path):
                os.remove(monitor.texture_path)
            tga_path = monitor.texture_path.replace(".psd", ".tga")
            if os.path.exists(tga_path):
                os.remove(tga_path)

    def stop_monitor(self, monitor: TextureMonitor) -> None:
        if monitor in self.texture_monitors:
            monitor.stop()
            self.texture_monitors.remove(monitor)

    def open_selected(self) -> None:
        """在 Photoshop 中打开选中的贴图。"""
        ps_path = self._find_photoshop()
        if not ps_path:
            return
        export_path = self._export_texture()
        if export_path is None:
            return
        self._launch_photoshop(ps_path, export_path)

    def open_selected_as_png(self) -> None:
        """以 PNG 格式在 Photoshop 中打开选中的贴图（保留透明通道，适合 UI 贴图）。"""
        ps_path = self._find_photoshop()
        if not ps_path:
            return
        export_path = self._export_texture_as_png()
        if export_path is None:
            return
        self._launch_photoshop(ps_path, export_path)

    def _export_texture_as_png(self) -> Optional[List[Tuple[str, str]]]:
        """直接导出选中的贴图为 PNG（不经过 TGA/PSD 转换，透明通道完整保留）。"""
        assets = unreal.EditorUtilityLibrary.get_selected_assets()
        texture_assets = [a for a in assets if isinstance(a, unreal.Texture2D)]

        if not texture_assets:
            unreal.EditorDialog.show_message(
                title="错误",
                message="请选择一个贴图资产",
                message_type=unreal.AppMsgType.OK,
            )
            return None

        request = []
        temp_dir = os.environ.get("TEMP", "")
        for asset in texture_assets:
            png_temp_path = os.path.join(temp_dir, f"{asset.get_name()}.png")

            task = unreal.AssetExportTask()
            task.set_editor_property("automated", True)
            task.set_editor_property("filename", png_temp_path)
            task.set_editor_property("object", asset)
            task.set_editor_property("prompt", False)
            task.set_editor_property("exporter", unreal.TextureExporterPNG())
            unreal.Exporter.run_asset_export_task(task)

            request.append((png_temp_path, asset.get_path_name()))

        return request

    def _save_to_psd(self, tga_path: str, save_path: str) -> None:
        image = Image.open(tga_path)
        image_obj = image.convert("RGBA")
        psd = PSDImage.frompil(image_obj)
        psd.save(save_path)
        image.close()

    def _export_texture(self) -> Optional[List[Tuple[str, str]]]:
        """导出选中的贴图为 PSD 文件。"""
        assets = unreal.EditorUtilityLibrary.get_selected_assets()
        texture_assets = [a for a in assets if isinstance(a, unreal.Texture2D)]

        if not texture_assets:
            unreal.EditorDialog.show_message(
                title="错误",
                message="请选择一个贴图资产",
                message_type=unreal.AppMsgType.OK,
            )
            return None

        request = []
        temp_dir = os.environ.get("TEMP", "")
        for asset in texture_assets:
            temp_path = os.path.join(temp_dir, f"{asset.get_name()}.tga")
            psd_temp_path = os.path.join(temp_dir, f"{asset.get_name()}.psd")

            task = unreal.AssetExportTask()
            task.set_editor_property("automated", True)
            task.set_editor_property("filename", temp_path)
            task.set_editor_property("object", asset)
            task.set_editor_property("prompt", False)
            task.set_editor_property("exporter", unreal.TextureExporterTGA())
            unreal.Exporter.run_asset_export_task(task)

            self._save_to_psd(temp_path, psd_temp_path)
            request.append((psd_temp_path, asset.get_path_name()))

        return request

    def _find_photoshop(self) -> Optional[str]:
        """查找 Photoshop 安装路径。"""
        if PHOTOSHOP_CUSTOM_PATH and os.path.exists(PHOTOSHOP_CUSTOM_PATH):
            adobe_path = PHOTOSHOP_CUSTOM_PATH
        else:
            adobe_path = PHOTOSHOP_DEFAULT_PATH

        for root, _, files in os.walk(adobe_path):
            if "photoshop.exe" in (f.lower() for f in files):
                return os.path.join(root, "photoshop.exe")

        if adobe_path != PHOTOSHOP_DEFAULT_PATH:
            for root, _, files in os.walk(PHOTOSHOP_DEFAULT_PATH):
                if "photoshop.exe" in (f.lower() for f in files):
                    return os.path.join(root, "photoshop.exe")

        unreal.EditorDialog.show_message(
            title="错误",
            message="未找到Photoshop安装路径，请检查安装或配置自定义路径",
            message_type=unreal.AppMsgType.OK,
        )
        return None

    def _launch_photoshop(
        self, ps_path: str, texture_path: List[Tuple[str, str]]
    ) -> None:
        """启动 Photoshop 并监控贴图变化。"""
        command = [ps_path] + [item[0] for item in texture_path]
        process = subprocess.Popen(command)
        for item in texture_path:
            self.texture_monitors.append(
                TextureMonitor(item[0], item[1], self, process)
            )
