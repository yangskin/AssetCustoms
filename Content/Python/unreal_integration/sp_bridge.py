"""Substance Painter Bridge — UE 侧数据收集、导出与发送。

职责：
  ① collect_material_info() — 遍历 StaticMesh 材质槽 + 贴图参数 → JSON
  ② export_mesh_fbx() — StaticMeshExporterFBX → 临时目录
  ③ export_textures() — AssetExportTask → TGA
  ④ send_to_sp() — 打包数据 + 调用 RemotePainter 执行 SP 端脚本
  ⑤ 自动发现并拉起 Substance Painter（含 --enable-remote-scripting）

纯逻辑函数（可 pytest）与 UE API 函数分离。
"""
import json
import os
import subprocess
from typing import Any


# ---------------------------------------------------------------------------
# 纯逻辑函数（🤖 可 pytest）
# ---------------------------------------------------------------------------

def build_material_info_json(
    static_mesh_name: str,
    static_mesh_path: str,
    materials: list[dict],
) -> str:
    """将材质信息序列化为 JSON 字符串。

    Args:
        static_mesh_name: StaticMesh 资产名（如 "SM_Chair"）。
        static_mesh_path: UE 资产路径（如 "/Game/Meshes/SM_Chair"）。
        materials: 材质信息列表，每个元素包含 material_name, material_path, textures。

    Returns:
        格式化的 JSON 字符串。
    """
    data = {
        "static_mesh": static_mesh_name,
        "static_mesh_path": static_mesh_path,
        "materials": materials,
    }
    return json.dumps(data, indent=4, ensure_ascii=False)


def parse_material_info_json(json_str: str) -> dict:
    """解析材质信息 JSON。

    Args:
        json_str: build_material_info_json() 输出的 JSON 字符串。

    Returns:
        解析后的字典。

    Raises:
        ValueError: JSON 缺少必填字段。
    """
    data = json.loads(json_str)
    for field in ("static_mesh", "static_mesh_path", "materials"):
        if field not in data:
            raise ValueError(f"材质信息 JSON 缺少必填字段: {field}")
    return data


def collect_texture_paths(material_info: dict) -> set[str]:
    """从材质信息中提取所有不重复的贴图路径。

    Args:
        material_info: parse_material_info_json() 返回的字典。

    Returns:
        贴图 UE 资产路径集合。
    """
    paths: set[str] = set()
    for mat in material_info.get("materials", []):
        for tex in mat.get("textures", []):
            path = tex.get("texture_path", "")
            if path:
                paths.add(path)
    return paths


def update_texture_export_paths(material_info: dict, export_map: dict[str, str]) -> dict:
    """更新材质信息中每个贴图的导出路径。

    Args:
        material_info: 材质信息字典。
        export_map: UE 资产路径 → 本地导出路径的映射。

    Returns:
        更新后的材质信息字典（原地修改+返回）。
    """
    for mat in material_info.get("materials", []):
        for tex in mat.get("textures", []):
            ue_path = tex.get("texture_path", "")
            if ue_path in export_map:
                tex["texture_export_path"] = export_map[ue_path]
    return material_info


def update_texture_sizes_from_exports(material_info: dict) -> dict:
    """从导出文件读取实际像素尺寸并更新 texture_size。

    AssetExportTask 以源分辨率导出，而 blueprint_get_size_x/y() 返回的是
    受 max_texture_size / LOD bias 影响的运行时尺寸。此函数以导出文件为准
    覆盖 texture_size，确保 SP 端拿到真实分辨率。

    Returns:
        更新后的材质信息字典（原地修改+返回）。
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return material_info

    for mat in material_info.get("materials", []):
        for tex in mat.get("textures", []):
            export_path = tex.get("texture_export_path", "")
            if not export_path or not os.path.isfile(export_path):
                continue
            try:
                with Image.open(export_path) as img:
                    w, h = img.size
                    tex["texture_size"] = max(w, h)
            except Exception:
                pass  # 保留 blueprint_get_size_x/y 的值作为 fallback
    return material_info


def build_sp_script(material_info_json: str, mesh_export_path: str) -> str:
    """构建发送到 SP 端执行的 Python 脚本。

    脚本在 SP Remote Scripting 环境执行，
    调用 SPsync 的 sp_receive.receive_from_ue()。

    Args:
        material_info_json: 材质信息 JSON 字符串。
        mesh_export_path: FBX 文件的本地绝对路径。

    Returns:
        完整的 Python 脚本字符串。
    """
    # 使用 json.dumps 安全嵌入字符串（自动处理所有转义字符）
    import json as _json
    safe_json = _json.dumps(material_info_json)
    safe_mesh = _json.dumps(mesh_export_path)

    # 注意：不使用 threading — SP Python API 非线程安全，
    # 必须在主线程执行。UE 侧 fire-and-forget 超时后会优雅处理。
    script = (
        "try:\n"
        "    import substance_painter_plugins\n"
        "    receive_fn = substance_painter_plugins.plugins['SPsync'].receive_from_ue\n"
        f"    json_data = {safe_json}\n"
        f"    mesh_path = {safe_mesh}\n"
        "    receive_fn(json_data, mesh_path)\n"
        "except Exception as e:\n"
        "    import traceback\n"
        "    traceback.print_exc()\n"
    )
    return script


# ---------------------------------------------------------------------------
# SP 发现 — 纯逻辑（🤖 可 pytest）
# ---------------------------------------------------------------------------

# 环境变量优先；未设置时回退到 Program Files 默认路径
SP_ENV_KEY = "THM_SP_ROOT"
SP_DEFAULT_DIR = os.path.join(
    os.environ.get("PROGRAMFILES", r"C:\Program Files"),
    "Adobe", "Adobe Substance 3D Painter",
)
SP_EXE_NAME = "Adobe Substance 3D Painter.exe"


def find_sp_executable(
    custom_dir: str | None = None,
    default_dir: str = SP_DEFAULT_DIR,
    exe_name: str = SP_EXE_NAME,
) -> str | None:
    """在给定目录树中查找 Substance Painter 可执行文件。

    查找顺序：
    1. custom_dir（环境变量 / 用户配置）
    2. default_dir（Program Files 默认路径）

    Args:
        custom_dir: 自定义安装根目录（None 则跳过）。
        default_dir: 默认安装根目录。
        exe_name: 可执行文件名（不区分大小写）。

    Returns:
        可执行文件的绝对路径，未找到返回 None。
    """
    exe_lower = exe_name.lower()

    dirs_to_search: list[str] = []
    if custom_dir and os.path.isdir(custom_dir):
        dirs_to_search.append(custom_dir)
    if default_dir and os.path.isdir(default_dir) and default_dir not in dirs_to_search:
        dirs_to_search.append(default_dir)

    for search_root in dirs_to_search:
        for root, _dirs, files in os.walk(search_root):
            for f in files:
                if f.lower() == exe_lower:
                    return os.path.join(root, f)
    return None


# ---------------------------------------------------------------------------
# UE API 函数（👁️ 需在 UE 编辑器中人工测试）
# ---------------------------------------------------------------------------

def _get_temp_dir() -> str:
    """返回临时导出目录。"""
    return os.environ.get("TEMP", os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp"))


class SPBridge:
    """Substance Painter 发送桥接。

    功能流程：
    1. 自动发现并拉起 Substance Painter（若未运行）
    2. 等待 SP Remote Scripting 端口就绪
    3. 收集选中 StaticMesh 的材质/贴图信息
    4. 导出 FBX + 贴图到临时目录
    5. 通过 RemotePainter 发送到 SP
    """

    # 等待 SP 就绪的最大轮询次数（每次间隔 ~1s，总计 ≈ SP_WAIT_ROUNDS 秒）
    SP_WAIT_ROUNDS = 180

    def __init__(self):
        self._remote = None
        self._sp_process = None  # subprocess.Popen handle，防止 ResourceWarning

    def _ensure_remote(self):
        """延迟初始化 RemotePainter。"""
        if self._remote is None:
            from unreal_integration.sp_remote import RemotePainter
            self._remote = RemotePainter()

    def _ensure_sp_running(self) -> bool:
        """确保 SP 已启动且 Remote Scripting 可达。

        流程：
        1. 检测已有连接 → 直接返回
        2. 查找 SP 可执行文件 → 未找到则弹窗报错
        3. 启动 SP（--enable-remote-scripting）
        4. ScopedSlowTask 进度条等待连接

        Returns:
            True 表示 SP 就绪，False 表示失败（弹窗已提示用户）。
        """
        import unreal

        self._ensure_remote()

        # 已就绪（能执行脚本） → 直接通过
        if self._remote.is_ready():
            return True

        # 查找可执行文件
        custom_dir = os.environ.get(SP_ENV_KEY, "") or None
        sp_exe = find_sp_executable(custom_dir=custom_dir)
        if sp_exe is None:
            unreal.EditorDialog.show_message(
                title="Send to Substance Painter",
                message=(
                    "未找到 Substance Painter 安装路径。\n\n"
                    f"请确认已安装，或设置环境变量 {SP_ENV_KEY} 指向安装目录。"
                ),
                message_type=unreal.AppMsgType.OK,
            )
            return False

        # 启动 SP
        unreal.log(f"[AssetCustoms] 启动 Substance Painter: {sp_exe}")
        self._sp_process = subprocess.Popen([sp_exe, "--enable-remote-scripting"])

        # 等待 Remote Scripting 就绪（每轮间隔 1s，避免空循环瞬间跑完）
        import time
        with unreal.ScopedSlowTask(self.SP_WAIT_ROUNDS, "等待 Substance Painter 连接...") as task:
            task.make_dialog(True)
            for i in range(self.SP_WAIT_ROUNDS):
                if task.should_cancel():
                    unreal.log_warning("[AssetCustoms] 用户取消了等待 SP 连接")
                    return False

                # 检查 SP 进程是否已退出（启动失败）
                if self._sp_process and self._sp_process.poll() is not None:
                    rc = self._sp_process.returncode
                    unreal.log_error(f"[AssetCustoms] Substance Painter 进程已退出 (exit code={rc})")
                    unreal.EditorDialog.show_message(
                        title="Send to Substance Painter",
                        message=f"Substance Painter 启动失败（exit code={rc}）。\n请检查安装或尝试手动启动。",
                        message_type=unreal.AppMsgType.OK,
                    )
                    return False

                if self._remote.is_ready():
                    unreal.log(f"[AssetCustoms] Substance Painter 连接成功且脚本引擎就绪（等待 {i} 秒）")
                    return True

                # 每 10 秒输出一次诊断日志
                if i > 0 and i % 10 == 0:
                    tcp_ok = self._remote.is_connected()
                    unreal.log(f"[AssetCustoms] 等待 SP... {i}/{self.SP_WAIT_ROUNDS}s TCP={tcp_ok}")

                task.enter_progress_frame(1)
                time.sleep(1)

        # 超时
        unreal.EditorDialog.show_message(
            title="Send to Substance Painter",
            message="等待 Substance Painter 连接超时，请手动启动后重试。",
            message_type=unreal.AppMsgType.OK,
        )
        return False

    def send_selected(self) -> None:
        """发送选中的 StaticMesh 到 Substance Painter。"""
        import unreal
        import traceback
        from unreal_integration.sp_remote import ConnectionError as SPConnectionError

        try:
            self._send_selected_impl(unreal, SPConnectionError)
        except Exception:
            unreal.log_error(f"[AssetCustoms] send_selected 未捕获异常:\n{traceback.format_exc()}")

    def _send_selected_impl(self, unreal, SPConnectionError) -> None:
        """send_selected 的实际实现（外层已有 try/except 保护）。"""
        # ── 前置校验：选中资产必须是 StaticMesh 或 SkeletalMesh ──
        # 优先从 Content Browser 获取
        assets = unreal.EditorUtilityLibrary.get_selected_assets()
        mesh = None
        for asset in assets:
            if isinstance(asset, (unreal.StaticMesh, unreal.SkeletalMesh)):
                mesh = asset
                break

        # 回退：从 Level Editor 选中的 Actor 提取 StaticMesh
        if mesh is None:
            mesh = self._extract_mesh_from_selected_actors(unreal)

        if mesh is None:
            unreal.EditorDialog.show_message(
                title="Send to Substance Painter",
                message=(
                    "请先选择一个 StaticMesh / SkeletalMesh 资产，\n"
                    "或在关卡中选中包含 StaticMeshComponent 的 Actor。"
                ),
                message_type=unreal.AppMsgType.OK,
            )
            return

        # 收集数据（在连接 SP 之前先检查配置，避免无配置时白等连接）
        unreal.log("[AssetCustoms] [1/6] 收集材质信息...")
        material_info_json = self._collect_material_info(mesh)
        if material_info_json is None:
            return

        material_info = parse_material_info_json(material_info_json)

        # ── 配置检查：至少需要一个有效的 config_profile ──
        if not self._has_valid_config(material_info):
            unreal.EditorDialog.show_message(
                title="Send to Substance Painter",
                message=(
                    "无法导出：选中资产没有关联的 AssetCustoms 配置。\n\n"
                    "缺少材质/贴图相关定义信息，SP 端无法正确接收。\n"
                    "请先通过右键菜单 → Config Profile → Set 为资产\n"
                    "（StaticMesh 或 MaterialInstance）指定配置文件。\n\n"
                    "Export blocked: no AssetCustoms config profile found.\n"
                    "Please assign a config profile to the mesh or its materials\n"
                    "via right-click → Config Profile → Set."
                ),
                message_type=unreal.AppMsgType.OK,
            )
            return

        # 确保 SP 已启动并连接
        unreal.log("[AssetCustoms] [2/6] 检查 SP 连接...")
        if not self._ensure_sp_running():
            return

        # 导出 FBX
        unreal.log("[AssetCustoms] [3/6] 导出 FBX...")
        mesh_path = self._export_mesh_fbx(mesh)
        if mesh_path is None:
            return

        # 导出贴图
        unreal.log("[AssetCustoms] [4/6] 导出贴图...")
        texture_paths = collect_texture_paths(material_info)
        export_map = self._export_textures(texture_paths)
        update_texture_export_paths(material_info, export_map)
        update_texture_sizes_from_exports(material_info)

        # 重新序列化（含导出路径）
        updated_json = json.dumps(material_info, indent=4, ensure_ascii=False)

        # 构建并发送脚本（fire-and-forget：SP 端异步执行，不阻塞 UE 主线程）
        unreal.log("[AssetCustoms] [5/6] 构建 SP 脚本...")
        script = build_sp_script(updated_json, mesh_path)

        unreal.log("[AssetCustoms] [6/6] 发送到 SP...")
        try:
            self._remote.execute_fire_and_forget(script)
            # SP 脚本同步执行，fire-and-forget 会在超时后返回
            # 无论是否超时，SP 都会继续执行脚本
            unreal.log("[AssetCustoms] 已发送到 Substance Painter，SP 端正在处理...")
        except SPConnectionError as exc:
            unreal.log_error(f"[AssetCustoms] SP 连接失败: {exc}")
        except Exception as exc:
            unreal.log_error(f"[AssetCustoms] SP 脚本执行失败: {exc}")

    @staticmethod
    def _extract_mesh_from_selected_actors(unreal):
        """从 Level Editor 选中的 Actor 中提取 StaticMesh 资产。

        遍历选中的 Actor，查找第一个包含 StaticMeshComponent 且绑定了
        有效 StaticMesh 资产的组件，返回该 StaticMesh。

        Returns:
            StaticMesh 或 None。
        """
        try:
            subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        except Exception:
            return None
        if subsystem is None:
            return None

        actors = subsystem.get_selected_level_actors()
        if not actors:
            return None

        for actor in actors:
            comps = actor.get_components_by_class(unreal.StaticMeshComponent)
            for comp in comps:
                mesh = comp.static_mesh
                if mesh is not None:
                    unreal.log(
                        f"[AssetCustoms] Level Editor: 从 Actor '{actor.get_actor_label()}' "
                        f"提取 StaticMesh '{mesh.get_name()}'"
                    )
                    return mesh

        return None

    @staticmethod
    def _has_valid_config(material_info: dict) -> bool:
        """检查材质信息中是否至少有一个有效的配置。

        如果顶层或任意材质条目包含 config_profile，视为有配置。

        Args:
            material_info: parse_material_info_json() 返回的字典。

        Returns:
            True 表示有至少一个有效配置，False 表示完全无配置。
        """
        if material_info.get("config_profile"):
            return True
        for mat in material_info.get("materials", []):
            if mat.get("config_profile"):
                return True
        return False

    def _collect_material_info(self, mesh) -> str | None:
        """遍历选中 Mesh 的材质槽收集信息。

        每个 MI 独立读取 AssetCustoms_ConfigProfile tag，加载对应配置，
        将 parameter_bindings / config_profile 注入到各 materials[] 元素中。
        Mesh 级别的 tag 作为顶层 fallback（兼容无 MI tag 的情况）。

        支持 StaticMesh 和 SkeletalMesh。
        """
        import unreal

        sm_name = mesh.get_name()
        sm_path = unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(mesh)
        is_skeletal = isinstance(mesh, unreal.SkeletalMesh)
        mesh_type = "SkeletalMesh" if is_skeletal else "StaticMesh"
        unreal.log(f"[AssetCustoms][SP] {mesh_type}={sm_name}  path={sm_path}")

        # ── Mesh 级别 Config Profile tag（作为 fallback）──
        sm_bindings: dict[str, str] = {}
        sm_tex_defs: list[dict] = []
        sm_profile_name = ""
        try:
            tag_value = unreal.EditorAssetLibrary.get_metadata_tag(mesh, "AssetCustoms_ConfigProfile")
            if tag_value:
                sm_profile_name = tag_value
                unreal.log(f"[AssetCustoms][SP] {mesh_type} ConfigProfile tag = '{sm_profile_name}'")
                sm_bindings, sm_tex_defs = self._load_config_for_sp(sm_profile_name, unreal)
            else:
                unreal.log(f"[AssetCustoms][SP] {mesh_type} 无 ConfigProfile tag")
        except Exception as e:
            unreal.log_warning(f"[AssetCustoms][SP] 读取 {mesh_type} ConfigProfile tag 失败: {e}")

        if is_skeletal:
            skeletal_materials = mesh.materials
            material_num = len(skeletal_materials)
        else:
            sm_subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
            material_num = sm_subsystem.get_number_materials(mesh)
        static_materials = mesh.materials if is_skeletal else mesh.static_materials
        materials_list = []

        for i in range(material_num):
            material = mesh.get_material(i)
            if not material or not isinstance(material, unreal.MaterialInterface):
                continue

            slot_name = str(static_materials[i].material_slot_name) if i < len(static_materials) else f"Material_{i}"

            if isinstance(material, unreal.MaterialInstance):
                mat_name = material.get_name()
                mat_path = unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(material)
                unreal.log(f"[AssetCustoms][SP]   材质[{i}] slot={slot_name}  name={mat_name}  path={mat_path}")

                # ── 读取 MI 级别 Config Profile tag ──
                mi_bindings: dict[str, str] = {}
                mi_tex_defs: list[dict] = []
                mi_profile_name = ""
                try:
                    mi_tag = unreal.EditorAssetLibrary.get_metadata_tag(material, "AssetCustoms_ConfigProfile")
                    if mi_tag:
                        mi_profile_name = mi_tag
                        unreal.log(f"[AssetCustoms][SP]     MI ConfigProfile = '{mi_profile_name}'")
                        mi_bindings, mi_tex_defs = self._load_config_for_sp(mi_profile_name, unreal)
                    else:
                        unreal.log(f"[AssetCustoms][SP]     MI 无 ConfigProfile tag，使用 SM fallback")
                except Exception as e:
                    unreal.log_warning(f"[AssetCustoms][SP]     读取 MI ConfigProfile tag 失败: {e}")

                texture_params = material.get_editor_property("texture_parameter_values")

                textures = []
                for param in texture_params:
                    info = param.get_editor_property("parameter_info")
                    prop_name = str(info.name)  # unreal.Name → str，确保 JSON 可序列化
                    texture = param.get_editor_property("parameter_value")
                    if texture and isinstance(texture, unreal.Texture2D):
                        tex_path = unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(texture)
                        tex_name = texture.get_name()
                        tex_size_x = texture.blueprint_get_size_x()
                        tex_size_y = texture.blueprint_get_size_y()
                        unreal.log(f"[AssetCustoms][SP]     贴图 param={prop_name}  name={tex_name}  size={tex_size_x}x{tex_size_y}")
                        textures.append({
                            "texture_property_name": prop_name,
                            "texture_path": tex_path,
                            "texture_export_path": "",
                            "texture_name": tex_name,
                            "texture_size": max(tex_size_x, tex_size_y),
                        })

                mat_entry: dict = {
                    "material_name": mat_name,
                    "material_slot_name": slot_name,
                    "material_path": mat_path,
                    "textures": textures,
                }
                # 注入 per-MI 的 bindings 和 texture_definitions（优先 MI 自身 tag，fallback SM tag）
                effective_bindings = mi_bindings or sm_bindings
                effective_tex_defs = mi_tex_defs or sm_tex_defs
                effective_profile = mi_profile_name or sm_profile_name
                if effective_bindings:
                    mat_entry["parameter_bindings"] = effective_bindings
                if effective_tex_defs:
                    mat_entry["texture_definitions"] = effective_tex_defs
                if effective_profile:
                    mat_entry["config_profile"] = effective_profile

                materials_list.append(mat_entry)

        # ── 构建 JSON ──
        data: dict = {
            "static_mesh": sm_name,
            "static_mesh_path": sm_path,
            "materials": materials_list,
        }
        # SM 级别 bindings + texture_definitions 作为顶层 fallback（兼容旧版 SP 侧）
        if sm_bindings:
            data["parameter_bindings"] = sm_bindings
            unreal.log(f"[AssetCustoms][SP] SM fallback parameter_bindings: {sm_bindings}")
        if sm_tex_defs:
            data["texture_definitions"] = sm_tex_defs
        if sm_profile_name:
            data["config_profile"] = sm_profile_name

        return json.dumps(data, indent=4, ensure_ascii=False)

    @staticmethod
    def _load_config_for_sp(profile_name: str, unreal) -> tuple[dict[str, str], list[dict]]:
        """根据 profile 名加载配置并返回 (parameter_bindings, texture_definitions)。"""
        import os
        from core.config.loader import load_config

        # 搜索配置文件（与 ui.py._scan_config_presets 相同逻辑）
        search_dirs = []
        try:
            _here = os.path.abspath(__file__)
            _plugin_content = os.path.dirname(os.path.dirname(os.path.dirname(_here)))
            search_dirs.append(os.path.join(_plugin_content, "Config", "AssetCustoms"))
        except Exception:
            pass
        try:
            content_dir = unreal.Paths.project_content_dir()
            search_dirs.append(os.path.join(content_dir, "Config", "AssetCustoms"))
        except Exception:
            pass

        for cfg_dir in search_dirs:
            for ext in (".jsonc", ".json"):
                cfg_path = os.path.join(cfg_dir, f"{profile_name}{ext}")
                if os.path.isfile(cfg_path):
                    config = load_config(cfg_path)
                    bindings = dict(config.output.material.parameter_bindings)
                    # 将 texture_definitions 序列化为可 JSON 化的 dict 列表
                    tex_defs = []
                    for td in config.processing.texture_definitions:
                        channels_dict = {}
                        for k, v in td.channels.items():
                            if hasattr(v, '__dataclass_fields__'):
                                # ChannelDef dataclass → 只保留 JSON 需要的字段
                                ch_d: dict = {"ch": v.ch}
                                if v.source:
                                    ch_d["from"] = v.source
                                if v.constant is not None:
                                    ch_d["constant"] = v.constant
                                channels_dict[k] = ch_d
                            elif isinstance(v, dict):
                                channels_dict[k] = dict(v)
                            else:
                                channels_dict[k] = v
                        td_dict = {
                            "suffix": td.suffix,
                            "name": td.name,
                            "channels": channels_dict,
                        }
                        # 使用交付阶段的 max_resolution（output defaults + overrides）
                        output_defaults = config.output.texture_import_defaults
                        resolved_max_res = output_defaults.max_resolution
                        suffix_overrides = config.output.texture_import_overrides.get(td.suffix, {})
                        if "max_resolution" in suffix_overrides:
                            resolved_max_res = suffix_overrides["max_resolution"]
                        if resolved_max_res:
                            td_dict["max_resolution"] = resolved_max_res
                        tex_defs.append(td_dict)
                    unreal.log(f"[AssetCustoms][SP] 已加载配置 {cfg_path}")
                    unreal.log(f"[AssetCustoms][SP]   parameter_bindings = {bindings}")
                    unreal.log(f"[AssetCustoms][SP]   texture_definitions = {len(tex_defs)} 个")
                    return bindings, tex_defs

        unreal.log_warning(f"[AssetCustoms][SP] 未找到配置文件: {profile_name}")
        return {}, []

    def _export_mesh_fbx(self, mesh) -> str | None:
        """导出 StaticMesh 或 SkeletalMesh 为 FBX。"""
        import unreal

        export_path = os.path.join(_get_temp_dir(), f"{mesh.get_name()}.fbx")

        is_skeletal = isinstance(mesh, unreal.SkeletalMesh)
        if is_skeletal:
            exporter = unreal.SkeletalMeshExporterFBX()
        else:
            exporter = unreal.StaticMeshExporterFBX()

        options = unreal.FbxExportOption()
        options.set_editor_property("level_of_detail", False)
        options.set_editor_property("vertex_color", True)
        options.set_editor_property("ascii", True)
        options.set_editor_property("force_front_x_axis", False)
        options.set_editor_property("fbx_export_compatibility", unreal.FbxExportCompatibility.FBX_2016)
        options.set_editor_property("collision", False)

        task = unreal.AssetExportTask()
        task.set_editor_property("object", mesh)
        task.set_editor_property("automated", True)
        task.set_editor_property("filename", export_path)
        task.set_editor_property("options", options)
        task.set_editor_property("exporter", exporter)

        unreal.Exporter.run_asset_export_task(task)
        return export_path

    # HDR compression settings — 这些对应的 source format 是 HDR (float)，
    # TGA 不支持，需用 EXR。
    _HDR_COMPRESSION = frozenset()  # 延迟初始化（需要 unreal 模块）

    @classmethod
    def _get_hdr_compression(cls):
        """返回 HDR 类型的 TextureCompressionSettings 集合。"""
        if not cls._HDR_COMPRESSION:
            import unreal
            cs = unreal.TextureCompressionSettings
            cls._HDR_COMPRESSION = frozenset([
                cs.TC_HDR,
                cs.TC_HDR_COMPRESSED,
                cs.TC_HALF_FLOAT,
                cs.TC_SINGLE_FLOAT,
                cs.TC_HDR_F32,
            ])
        return cls._HDR_COMPRESSION

    @staticmethod
    def _run_export(texture, export_path):
        """执行一次贴图导出（不指定 exporter，由 UE 根据扩展名自动匹配）。"""
        import unreal

        task = unreal.AssetExportTask()
        task.set_editor_property("automated", True)
        task.set_editor_property("filename", export_path)
        task.set_editor_property("object", texture)
        task.set_editor_property("prompt", False)
        # 不设置 exporter — UE 通过 FindExporter + SupportsObject
        # 自动选择兼容当前纹理源格式的导出器，避免 check(SupportsTexture) 断言崩溃
        return unreal.Exporter.run_asset_export_task(task)

    def _export_textures(self, texture_ue_paths: set[str]) -> dict[str, str]:
        """导出贴图到临时目录。

        策略（不显式指定 exporter，避免 SupportsTexture 断言崩溃）：
        - HDR（由 compression_settings 判断）→ .exr
        - 非 HDR → 先尝试 .tga（无 alpha 预乘），失败则回退 .png

        Returns:
            UE 资产路径 → 本地导出路径的映射。
        """
        import unreal

        export_map: dict[str, str] = {}
        temp_dir = _get_temp_dir()
        hdr_set = self._get_hdr_compression()

        for ue_path in texture_ue_paths:
            texture = unreal.EditorAssetLibrary.load_asset(ue_path)
            if not texture or not isinstance(texture, unreal.Texture2D):
                continue

            comp = texture.get_editor_property("compression_settings")
            is_hdr = comp in hdr_set
            name = texture.get_name()

            if is_hdr:
                export_path = os.path.join(temp_dir, f"{name}.exr")
                if self._run_export(texture, export_path):
                    export_map[ue_path] = os.path.abspath(export_path)
                else:
                    unreal.log_warning(f"[AssetCustoms] HDR 贴图导出失败: {ue_path}")
            else:
                # 优先 TGA（无 alpha 预乘），不支持时回退 PNG
                export_path = os.path.join(temp_dir, f"{name}.tga")
                if self._run_export(texture, export_path):
                    export_map[ue_path] = os.path.abspath(export_path)
                else:
                    export_path = os.path.join(temp_dir, f"{name}.png")
                    if self._run_export(texture, export_path):
                        export_map[ue_path] = os.path.abspath(export_path)
                        unreal.log_warning(
                            f"[AssetCustoms] TGA 不支持, 已回退 PNG: {ue_path}"
                        )
                    else:
                        unreal.log_warning(
                            f"[AssetCustoms] 贴图导出失败 (TGA+PNG): {ue_path}"
                        )

        return export_map
