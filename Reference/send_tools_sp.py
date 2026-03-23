"""
虚幻引擎贴图编辑工具。
提供贴图实时同步编辑功能。
"""

import unreal
import lib_remote
import os
import json
import psutil
import subprocess
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from pathlib import Path

# 配置项
SP_CUSTOM_PATH = os.environ.get('THM_SP_ROOT', "")  # 优先使用环境变量中的自定义sp安装路径
SP_DEFAULT_PATH = os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Adobe\\Adobe Substance 3D Painter')  # 默认sp安装路径

class TickTimer:
    """定时器基类，用于处理虚幻引擎的 tick 事件。
    tick事件是游戏引擎中按固定时间间隔执行的更新事件。
    """
    
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


class SPBridge():
    def __init__(self):
        self.sp_remote = lib_remote.RemotePainter()

        pass

    def is_remote_sp_running(self) -> bool:
        try:
            self.sp_remote.checkConnection()
            self.sp_remote.execScript("import substance_painter_plugins", "python")
            self.sp_remote.execScript("if substance_painter_plugins.is_plugin_started(substance_painter_plugins.plugins['ue_to_sp']) != True : substance_painter_plugins.start_plugin(substance_painter_plugins.plugins['ue_to_sp'])", "python")
            result = self.sp_remote.execScript("substance_painter_plugins.plugins['ue_to_sp'].UETOSPPORTPLUGIN.is_ready()", "python")
            return "True" in result
        except:
            return False


    def open_to_sp(self) -> None:

        sp_path = self._find_sp()
        if sp_path:
            if not self.is_remote_sp_running():
                self._launch_sp(sp_path)

            totalFrames = 2000
            textDisplay = "Wait substance painter Connect"
            with unreal.ScopedSlowTask(totalFrames, textDisplay) as ST:
                ST.make_dialog(True)       
                for i in range(totalFrames):
                    if self.is_remote_sp_running():
                        break
                    ST.enter_progress_frame(1)
            
            mesh_path = self._export_mesh(unreal.EditorUtilityLibrary.get_selected_assets()[0])
            material_info = self._export_material_info()
            texture_info = self._export_texture(material_info)

            texture_info_json = json.loads(texture_info)
            texture_info_json["static_mesh_path"] = Path(mesh_path).resolve()
            texture_info = json.dumps(texture_info_json, indent=4, ensure_ascii=False, default=self.custom_serializer)

            self._connect_sp_create_project(texture_info, self._get_material_templater_data())
                

    def _connect_sp_create_project(self, model_data:str, material_templater_data:str) -> None:
        model_data_str = "'" + model_data + "'"
        material_templater_data_str = "'" + material_templater_data + "'"
        
        self.sp_remote.execScript("import substance_painter_plugins", "python")
        python_script = f"substance_painter_plugins.plugins['ue_to_sp'].UETOSPPORTPLUGIN.from_data_create_project({model_data_str}, {material_templater_data_str})"

        python_script = python_script.replace("\n", "")
        python_script = python_script.replace("\\", "\\\\")
        self.sp_remote.checkConnection()
        result = self.sp_remote.execScript(python_script, "python")

        #print(result)

    def _get_material_templater_data(self) -> str:
        script_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_path, "environment_material_template.json")
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = file.read()
            return data
        except Exception as e:
            return None

    def _export_material_info(self) -> str:

        EditorStaticMeshLibrary = unreal.EditorStaticMeshLibrary()
        assets = unreal.EditorUtilityLibrary.get_selected_assets()
        static_mesh = None
        for asset in assets:
            if isinstance(asset, unreal.StaticMesh):
                static_mesh = asset
                break

        if static_mesh is None:
            unreal.EditorDialog.show_message(
            title='错误',
            message='请选择一个静态网格资产',
            message_type=unreal.AppMsgType.OK
            )
            return None

        # 获取所有引用的材质
        material_num = EditorStaticMeshLibrary.get_number_materials(static_mesh)
        material_assets = []
        for i in range(material_num):
            material = static_mesh.get_material(i)
            if material and isinstance(material, unreal.MaterialInterface):
                material_assets.append(material)

        # 收集材质信息
        material_info_list = []
        
        # 从材质中提取贴图资产
        texture_assets = []
        for material in material_assets:
            if isinstance(material, unreal.MaterialInstance):
                material_name = material.get_name()
                material_path = unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(material)
                material_path = material_path.replace("/", "\\")
                # 获取材质实例的贴图参数
                texture_params = material.get_editor_property('texture_parameter_values')
                
                material_textures = []
                for param in texture_params:
                    texture_info = param.get_editor_property('parameter_info')
                    texture_property_name = texture_info.name
                    
                    texture = param.get_editor_property('parameter_value')
                    if texture and isinstance(texture, unreal.Texture2D):
                        texture_path = unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(texture)
                        material_textures.append({
                            "texture_property_name": texture_property_name,
                            "texture_path": texture_path,
                            "texture_export_path": "",
                            "texture_name": texture.get_name()
                        })
                        
                        if texture not in texture_assets:
                            texture_assets.append(texture)
                
                # 添加材质信息到列表
                material_info_list.append({
                    "material_name": material_name,
                    "material_path": material_path,
                    "textures": material_textures
                })

        # 输出到JSON文件
        output_data = {
            "static_mesh": static_mesh.get_name(),
            "static_mesh_path": unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(static_mesh),
            "materials": material_info_list
        }
        #转换为json字符串
        output_data_json = json.dumps(output_data, indent=4, ensure_ascii=False, default=self.custom_serializer)

        return output_data_json

    def _export_texture(self, material_info_json: str):

        """导出选中的贴图或从 JSON 数据中提取贴图信息并导出"""

        # 从 JSON 数据中提取贴图信息
        material_info = json.loads(material_info_json)
        texture_paths = set()  # 用于去重
        for material in material_info.get("materials", []):
            for texture_info in material.get("textures", []):
                texture_paths.add(texture_info["texture_path"])
        
        # 加载贴图资产
        texture_assets = []
        for path in texture_paths:
            texture = unreal.EditorAssetLibrary.load_asset(path)
            if texture and isinstance(texture, unreal.Texture2D):
                texture_assets.append(texture)
        
        if len(texture_assets) == 0:
            unreal.EditorDialog.show_message(
                title='错误',
                message='JSON 数据中未找到有效的贴图资产',
                message_type=unreal.AppMsgType.OK
            )
            return None

        request = []

        for asset in texture_assets:
            export_path = os.path.join(os.environ.get('TEMP'), f"{asset.get_name()}.tga")
            task = unreal.AssetExportTask()
            task.set_editor_property('automated', True)
            task.set_editor_property('filename', export_path)
            task.set_editor_property('object', asset)
            task.set_editor_property('prompt', False)
            task.set_editor_property('exporter', unreal.TextureExporterTGA())
            unreal.Exporter.run_asset_export_task(task)
    
            export_path_pathlib = Path(export_path).resolve()
            request.append((str(export_path_pathlib), asset.get_path_name()))

        # 更新 JSON 数据中的贴图路径
        material_info = json.loads(material_info_json)
        for material in material_info.get("materials", []):
            for texture_info in material.get("textures", []):
                for path, original_path in request:
                    if texture_info["texture_path"] == original_path:
                        texture_info["texture_export_path"] = path  # 更新为导出后的路径
                        break

        # 将更新后的 JSON 数据转换回字符串
        updated_material_info_json = json.dumps(material_info, indent=4, ensure_ascii=False, default=self.custom_serializer)

        return updated_material_info_json
    
    def _export_mesh(self, mesh_asset:unreal.SkeletalMesh) -> str:
        export_path = os.path.join(os.environ.get('TEMP'), f"{mesh_asset.get_name()}.fbx")

        # 设置导出任务
        exportFbx: unreal.StaticMeshExporterFBX = unreal.StaticMeshExporterFBX()
        exportFbxOpt: unreal.FbxExportOption = unreal.FbxExportOption()

        exportFbxOpt.set_editor_property("level_of_detail", False)
        exportFbxOpt.set_editor_property("vertex_color", True)
        exportFbxOpt.set_editor_property("ascii", True)
        exportFbxOpt.set_editor_property("force_front_x_axis", True)
        exportFbxOpt.set_editor_property("fbx_export_compatibility", unreal.FbxExportCompatibility.FBX_2016)
        exportFbxOpt.set_editor_property("collision", False)

        export_task = unreal.AssetExportTask()
        export_task.set_editor_property("object", mesh_asset)
        export_task.set_editor_property('automated', True)
        export_task.set_editor_property("filename", export_path)

        export_task.set_editor_property("options", exportFbxOpt)
        export_task.set_editor_property("exporter", exportFbx)

        unreal.Exporter.run_asset_export_task(export_task)

        return export_path

    def _find_sp(self) -> str:
        """查找 sp 安装路径"""
        # 首先检查自定义路径
        if SP_CUSTOM_PATH and os.path.exists(SP_CUSTOM_PATH):
            adobe_path = SP_CUSTOM_PATH
        else:
            adobe_path = SP_DEFAULT_PATH

        print(adobe_path)
        
        # 在指定路径中查找Adobe Substance 3D Painter.exe
        for root, _, files in os.walk(adobe_path):
            for file in files:
                if file.lower() == 'adobe substance 3d painter.exe':
                    return os.path.join(root, file)
                
        # 如果在自定义路径中未找到，且使用的是自定义路径，则尝试默认路径
        if adobe_path != SP_DEFAULT_PATH:
            for root, _, files in os.walk(SP_DEFAULT_PATH):
                for file in files:
                    if file.lower() == 'adobe substance 3d painter.exe':
                        return os.path.join(root, file)
        
        # 如果都未找到，显示错误对话框
        unreal.EditorDialog.show_message(
            title='错误',
            message='未找到sp安装路径，请检查安装或配置自定义路径',
            message_type=unreal.AppMsgType.OK
        )
        return None

    def _launch_sp(self, ps_path: str) -> None:
        """启动 sp 并监控贴图变化"""

        # 组合命令行
        command = [ps_path]
        command.append("--enable-remote-scripting")

        # 启动sp    
        process = subprocess.Popen(command)

    def custom_serializer(self, obj):
        """自定义序列化函数，将无法序列化的对象转换为字符串"""
        if hasattr(obj, 'get_name'):
            return obj.get_name()
        if hasattr(obj, 'get_path_name'):
            return obj.get_path_name()
        return str(obj)  # 默认转换为字符串

#spb = SPBridge()
#spb.open_to_sp()







