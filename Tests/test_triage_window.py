"""
测试脚本：手动弹出 FR4 分诊窗口（使用模拟数据）。
用于在 UE 编辑器内验证分诊 UI 的外观和交互。
"""
import unreal
import importlib

# 重载相关模块以拿到最新代码
import unreal_qt
importlib.reload(unreal_qt)

from core.pipeline.check_chain import CheckFailure, CheckResult, CheckStatus
from core.textures.matcher import MatchResult
from core.pipeline import triage_ui
importlib.reload(triage_ui)
from core.pipeline.triage_ui import TriageWindow

# ---------------------------------------------------------------------------
# 构造模拟 CheckResult
# ---------------------------------------------------------------------------

mock_match_result = MatchResult(
    mapping={
        "BaseColor": "C:/Assets/T_Rock_BC.png",
        "Normal": "C:/Assets/T_Rock_N.png",
    },
    candidates={},
    orphans=[
        "C:/Assets/T_Rock_Extra.png",
        "C:/Assets/T_Rock_Unknown.tga",
    ],
    ambiguous_slots=["Roughness"],
    unmapped_slots=["Height", "AO"],
)

mock_check_result = CheckResult(
    status=CheckStatus.FAILED,
    failures=[
        CheckFailure(
            check_name="texture_mapping",
            reason="3 个逻辑位未完成映射: Roughness(歧义), Height, AO",
            details={"unmapped": ["Height", "AO"], "ambiguous": ["Roughness"]},
        ),
        CheckFailure(
            check_name="master_material",
            reason="母材质路径 /Game/Materials/MM_Test 不存在",
            details={"path": "/Game/Materials/MM_Test"},
        ),
    ],
    match_result=mock_match_result,
    static_mesh="SM_Rock",
)

# 模拟的贴图文件列表
all_textures = [
    "C:/Assets/T_Rock_BC.png",
    "C:/Assets/T_Rock_N.png",
    "C:/Assets/T_Rock_R.png",
    "C:/Assets/T_Rock_M.png",
    "C:/Assets/T_Rock_AO.png",
    "C:/Assets/T_Rock_H.png",
    "C:/Assets/T_Rock_Extra.png",
    "C:/Assets/T_Rock_Unknown.tga",
    "/Game/Textures/T_Embedded_Diffuse",
    "/Game/Textures/T_Embedded_Normal",
]

# ---------------------------------------------------------------------------
# 回调
# ---------------------------------------------------------------------------

def on_accept(decision):
    unreal.log(f"[TriageTest] 用户确认: accepted={decision.accepted}")
    unreal.log(f"[TriageTest]   base_name = {decision.base_name}")
    for slot, path in decision.corrected_mapping.items():
        unreal.log(f"[TriageTest]   {slot} -> {path}")

def on_cancel():
    unreal.log_warning("[TriageTest] 用户取消了分诊")

# ---------------------------------------------------------------------------
# 启动分诊窗口
# ---------------------------------------------------------------------------

unreal_qt.setup()

window = TriageWindow(
    check_result=mock_check_result,
    base_name="SM_Rock",
    all_texture_paths=all_textures,
    on_accept=on_accept,
    on_cancel=on_cancel,
)
window.show()
unreal_qt.wrap(window)

unreal.log("[TriageTest] FR4 分诊窗口已弹出 — 请查看!")
