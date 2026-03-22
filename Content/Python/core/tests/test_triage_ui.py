"""FR4 分诊 UI (triage_ui) 单元测试。

测试 TriageDecision 数据模型与 TriageWindow 构建/数据收集逻辑。
跳过需要 PySide6 的测试（CI 环境可能无 Qt）。
"""
import pytest

from core.pipeline.check_chain import CheckFailure, CheckResult, CheckStatus
from core.textures.matcher import MatchResult

# PySide6 可能不可用 —— 按需跳过
try:
    from PySide6 import QtWidgets  # noqa: F401
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

needs_qt = pytest.mark.skipif(not _HAS_QT, reason="PySide6 not available")


# ---------------------------------------------------------------------------
# TriageDecision 数据模型（纯 Python，无 Qt 依赖）
# ---------------------------------------------------------------------------

class TestTriageDecision:
    def test_default(self):
        from core.pipeline.triage_ui import TriageDecision
        d = TriageDecision()
        assert d.accepted is False
        assert d.corrected_mapping == {}
        assert d.base_name == ""

    def test_custom(self):
        from core.pipeline.triage_ui import TriageDecision
        d = TriageDecision(
            accepted=True,
            corrected_mapping={"BaseColor": "/path/T_D.png"},
            base_name="MyAsset",
        )
        assert d.accepted is True
        assert d.corrected_mapping == {"BaseColor": "/path/T_D.png"}
        assert d.base_name == "MyAsset"


# ---------------------------------------------------------------------------
# TriageWindow UI 测试（需要 PySide6）
# ---------------------------------------------------------------------------

@needs_qt
class TestTriageWindow:
    """测试 TriageWindow 的构建与数据收集逻辑。"""

    @pytest.fixture(autouse=True)
    def _setup_app(self):
        """确保 QApplication 存在。"""
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
        yield

    def _make_check_result(
        self,
        slot_mapping=None,
        unmapped=None,
        ambiguous=None,
        orphans=None,
        failures=None,
    ) -> CheckResult:
        mr = MatchResult(
            mapping=slot_mapping or {},
            candidates={},
            orphans=orphans or [],
            ambiguous_slots=ambiguous or [],
            unmapped_slots=unmapped or [],
        )
        return CheckResult(
            status=CheckStatus.FAILED,
            failures=failures or [CheckFailure("texture_mapping", "缺少贴图")],
            match_result=mr,
            static_mesh="SM_Test",
        )

    def test_window_creates(self):
        from core.pipeline.triage_ui import TriageWindow
        cr = self._make_check_result()
        w = TriageWindow(cr, "TestAsset", ["/tex/A.png", "/tex/B.png"])
        assert w.windowTitle() == "AssetCustoms — 分诊 (Triage)"
        w.close()

    def test_collect_mapping_empty(self):
        """无映射时 _collect_mapping 返回空字典。"""
        from core.pipeline.triage_ui import TriageWindow
        cr = self._make_check_result(unmapped=["BaseColor", "Normal"])
        w = TriageWindow(cr, "Test", ["/tex/A.png"])
        mapping = w._collect_mapping()
        # 所有 combo 默认为 "(未选择)" → 值为空 → 不入字典
        assert mapping == {}
        w.close()

    def test_collect_mapping_prefilled(self):
        """已匹配的 slot 应预填到下拉框。"""
        from core.pipeline.triage_ui import TriageWindow
        cr = self._make_check_result(
            slot_mapping={"BaseColor": "/tex/A.png"},
        )
        w = TriageWindow(cr, "Test", ["/tex/A.png", "/tex/B.png"])
        mapping = w._collect_mapping()
        assert mapping.get("BaseColor") == "/tex/A.png"
        w.close()

    def test_on_accept_callback(self):
        """点击"执行标准化"应触发 on_accept 回调。"""
        from core.pipeline.triage_ui import TriageWindow
        cr = self._make_check_result(
            slot_mapping={"BaseColor": "/tex/A.png"},
        )
        received = []
        w = TriageWindow(
            cr, "MyAsset", ["/tex/A.png"],
            on_accept=lambda d: received.append(d),
        )
        # 直接调用内部方法模拟按钮点击
        w._on_execute_clicked()
        assert len(received) == 1
        assert received[0].accepted is True
        assert received[0].base_name == "MyAsset"
        assert received[0].corrected_mapping.get("BaseColor") == "/tex/A.png"

    def test_on_cancel_callback(self):
        """点击"取消"应触发 on_cancel 回调。"""
        from core.pipeline.triage_ui import TriageWindow
        cr = self._make_check_result()
        cancelled = []
        w = TriageWindow(
            cr, "Test", [],
            on_cancel=lambda: cancelled.append(True),
        )
        w._on_cancel_clicked()
        assert len(cancelled) == 1

    def test_display_name(self):
        from core.pipeline.triage_ui import TriageWindow
        assert TriageWindow._display_name("/Game/Textures/T_Rock_D") == "T_Rock_D"
        assert TriageWindow._display_name("C:\\dir\\T_Rock_D.png") == "T_Rock_D.png"
        assert TriageWindow._display_name("simple.png") == "simple.png"
