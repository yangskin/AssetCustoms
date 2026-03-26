"""Tests for SPBridge._extract_mesh_from_selected_actors (M10).

使用 mock 替代 unreal 模块，验证从 Level Editor 选中 Actor 提取 StaticMesh 的逻辑。
"""
import sys
import os
import types
from unittest.mock import MagicMock
import pytest

# ── 路径 & mock 设置 ──
_CONTENT_PY = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "Content", "Python"))
sys.path.insert(0, _CONTENT_PY)

# mock unreal + sp_remote + photoshop_bridge 等（sp_bridge 导入链依赖）
_unreal_mock = types.ModuleType("unreal")
sys.modules.setdefault("unreal", _unreal_mock)

# mock unreal_integration 包——阻止 __init__.py 触发完整导入链
_ui_pkg = types.ModuleType("unreal_integration")
_ui_pkg.__path__ = [os.path.join(_CONTENT_PY, "unreal_integration")]  # type: ignore
sys.modules.setdefault("unreal_integration", _ui_pkg)

_sp_remote_mod = types.ModuleType("unreal_integration.sp_remote")
_sp_remote_mod.RemotePainter = MagicMock  # type: ignore
_sp_remote_mod.ConnectionError = type("ConnectionError", (Exception,), {})  # type: ignore
sys.modules.setdefault("unreal_integration.sp_remote", _sp_remote_mod)

# 直接导入 sp_bridge 模块（绕过 __init__.py 的其他依赖）
import importlib
_sp_bridge_spec = importlib.util.spec_from_file_location(
    "unreal_integration.sp_bridge",
    os.path.join(_CONTENT_PY, "unreal_integration", "sp_bridge.py"),
)
_sp_bridge_mod = importlib.util.module_from_spec(_sp_bridge_spec)
sys.modules["unreal_integration.sp_bridge"] = _sp_bridge_mod
_sp_bridge_spec.loader.exec_module(_sp_bridge_mod)

SPBridge = _sp_bridge_mod.SPBridge

_extract = SPBridge._extract_mesh_from_selected_actors


def _make_unreal():
    """构造含必要类型和子系统的 mock unreal 模块。"""
    u = MagicMock()
    u.StaticMesh = type("StaticMesh", (), {})
    u.SkeletalMesh = type("SkeletalMesh", (), {})
    u.StaticMeshComponent = type("StaticMeshComponent", (), {})
    return u


class TestExtractMeshFromSelectedActors:
    """验证 _extract_mesh_from_selected_actors 静态方法。"""

    # ---- 正常路径 ----

    def test_single_actor_single_sm(self):
        """单 Actor + 单 StaticMeshComponent → 返回 StaticMesh。"""
        u = _make_unreal()
        mesh = MagicMock()

        comp = MagicMock()
        comp.static_mesh = mesh

        actor = MagicMock()
        actor.get_components_by_class.return_value = [comp]
        actor.get_actor_label.return_value = "ChairActor"

        subsystem = MagicMock()
        subsystem.get_selected_level_actors.return_value = [actor]
        u.get_editor_subsystem.return_value = subsystem

        result = _extract(u)
        assert result is mesh
        u.get_editor_subsystem.assert_called_once_with(u.EditorActorSubsystem)

    def test_multi_actor_returns_first(self):
        """多个 Actor → 返回第一个有效 StaticMesh。"""
        u = _make_unreal()
        mesh1 = MagicMock()
        mesh2 = MagicMock()

        comp1 = MagicMock()
        comp1.static_mesh = mesh1
        comp2 = MagicMock()
        comp2.static_mesh = mesh2

        actor1 = MagicMock()
        actor1.get_components_by_class.return_value = [comp1]
        actor1.get_actor_label.return_value = "TableActor"
        actor2 = MagicMock()
        actor2.get_components_by_class.return_value = [comp2]
        actor2.get_actor_label.return_value = "ChairActor"

        subsystem = MagicMock()
        subsystem.get_selected_level_actors.return_value = [actor1, actor2]
        u.get_editor_subsystem.return_value = subsystem

        assert _extract(u) is mesh1

    def test_actor_with_multiple_sm_components(self):
        """单 Actor 含多个 SMC → 跳过 None mesh，返回第一个有效 mesh。"""
        u = _make_unreal()
        mesh = MagicMock()

        comp_empty = MagicMock()
        comp_empty.static_mesh = None
        comp_valid = MagicMock()
        comp_valid.static_mesh = mesh

        actor = MagicMock()
        actor.get_components_by_class.return_value = [comp_empty, comp_valid]
        actor.get_actor_label.return_value = "CharActor"

        subsystem = MagicMock()
        subsystem.get_selected_level_actors.return_value = [actor]
        u.get_editor_subsystem.return_value = subsystem

        assert _extract(u) is mesh

    # ---- 无效/边界路径 ----

    def test_no_actors_selected(self):
        """Level Editor 无选中 → 返回 None。"""
        u = _make_unreal()
        subsystem = MagicMock()
        subsystem.get_selected_level_actors.return_value = []
        u.get_editor_subsystem.return_value = subsystem

        assert _extract(u) is None

    def test_actor_without_sm_component(self):
        """Actor 无 StaticMeshComponent → 返回 None。"""
        u = _make_unreal()
        actor = MagicMock()
        actor.get_components_by_class.return_value = []

        subsystem = MagicMock()
        subsystem.get_selected_level_actors.return_value = [actor]
        u.get_editor_subsystem.return_value = subsystem

        assert _extract(u) is None

    def test_sm_component_with_null_mesh(self):
        """SMC 存在但绑定的 mesh 为 None → 返回 None。"""
        u = _make_unreal()
        comp = MagicMock()
        comp.static_mesh = None

        actor = MagicMock()
        actor.get_components_by_class.return_value = [comp]

        subsystem = MagicMock()
        subsystem.get_selected_level_actors.return_value = [actor]
        u.get_editor_subsystem.return_value = subsystem

        assert _extract(u) is None

    def test_subsystem_unavailable(self):
        """EditorActorSubsystem 不可用 → 返回 None。"""
        u = _make_unreal()
        u.get_editor_subsystem.return_value = None

        assert _extract(u) is None

    def test_get_editor_subsystem_raises(self):
        """get_editor_subsystem 抛异常 → 返回 None（不崩溃）。"""
        u = _make_unreal()
        u.get_editor_subsystem.side_effect = RuntimeError("subsystem fail")

        assert _extract(u) is None

    def test_skip_actors_without_mesh_continue_to_next(self):
        """第一个 Actor 无 mesh，第二个有 → 应返回第二个的 mesh。"""
        u = _make_unreal()
        mesh = MagicMock()

        actor_empty = MagicMock()
        actor_empty.get_components_by_class.return_value = []

        comp = MagicMock()
        comp.static_mesh = mesh
        actor_valid = MagicMock()
        actor_valid.get_components_by_class.return_value = [comp]
        actor_valid.get_actor_label.return_value = "BarrelActor"

        subsystem = MagicMock()
        subsystem.get_selected_level_actors.return_value = [actor_empty, actor_valid]
        u.get_editor_subsystem.return_value = subsystem

        assert _extract(u) is mesh
