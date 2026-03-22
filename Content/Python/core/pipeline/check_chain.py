"""自动化检查链（FR3）：静默验证导入资产是否满足标准化条件。

检查项（按顺序执行，任一失败则整体失败）：
1. 资产识别 — 隔离区中有且仅有 1 个 StaticMesh
2. 主材质检查 — master_material_path 为空则跳过；不为空则验证存在
3. 贴图映射 — 使用 matcher 匹配所有逻辑位；未完整映射则失败

输出 CheckResult：成功/失败、失败原因、贴图映射、孤儿列表。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from core.config.schema import PluginConfig
from core.textures.matcher import MatchResult, match_textures


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass
class CheckFailure:
    """单个检查失败的描述。"""
    check_name: str   # "asset_count" | "master_material" | "texture_mapping"
    reason: str
    details: Dict = field(default_factory=dict)


@dataclass
class CheckResult:
    """检查链的完整输出。"""
    status: CheckStatus = CheckStatus.PASSED
    failures: List[CheckFailure] = field(default_factory=list)
    # 贴图映射结果（即使失败也携带部分映射，供分诊 UI 预填）
    match_result: Optional[MatchResult] = None
    # 识别到的 StaticMesh 名称/路径
    static_mesh: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == CheckStatus.PASSED


def check_asset_count(
    asset_names: List[str],
    mesh_filter: Optional[Callable[[str], bool]] = None,
) -> tuple[Optional[str], Optional[CheckFailure]]:
    """检查 1：隔离区中有且仅有 1 个 StaticMesh。

    Args:
        asset_names: 隔离区中的资产名列表。
        mesh_filter: 可选回调，判断一个资产名是否是 StaticMesh。
                     默认按名称前缀 'SM_' 或 'StaticMesh' 做简易判定。

    Returns:
        (mesh_name, failure) — 成功时 failure=None，失败时 mesh_name 可能为 None。
    """
    if mesh_filter is None:
        def mesh_filter(name: str) -> bool:
            upper = name.upper()
            return upper.startswith("SM_") or "STATICMESH" in upper

    meshes = [n for n in asset_names if mesh_filter(n)]

    if len(meshes) == 0:
        return None, CheckFailure(
            check_name="asset_count",
            reason="隔离区中未找到 StaticMesh",
            details={"found": 0, "assets": asset_names},
        )
    if len(meshes) > 1:
        return meshes[0], CheckFailure(
            check_name="asset_count",
            reason=f"隔离区中找到 {len(meshes)} 个 StaticMesh（预期仅 1 个）",
            details={"found": len(meshes), "meshes": meshes},
        )
    return meshes[0], None


def check_master_material(
    material_path: str,
    exists_fn: Optional[Callable[[str], bool]] = None,
) -> Optional[CheckFailure]:
    """检查 2：验证主材质路径。

    - 空字符串：视为通过（跳过 MIC 创建）
    - 不为空但不存在：失败

    Args:
        material_path: default_master_material_path 的值。
        exists_fn: 检测 UE 资产是否存在的回调。默认始终返回 True（纯 Python 测试用）。
    """
    if not material_path:
        return None  # 空路径 = 跳过 MIC

    if exists_fn is None:
        exists_fn = lambda _: True  # noqa: E731

    if not exists_fn(material_path):
        return CheckFailure(
            check_name="master_material",
            reason=f"主材质不存在: {material_path}",
            details={"path": material_path},
        )
    return None


def check_texture_mapping(
    texture_files: List[str],
    config: PluginConfig,
) -> tuple[MatchResult, Optional[CheckFailure]]:
    """检查 3：贴图映射完整性。

    使用 matcher 匹配后，检查是否所有非 allow_missing 的输出项都有源贴图。

    Returns:
        (match_result, failure) — match_result 始终返回，failure 为 None 表示通过。
    """
    match_result = match_textures(texture_files, config.texture_input_rules)

    # 检查每个 enabled 的输出定义所需的逻辑位是否已映射
    missing_slots: List[str] = []
    for output_def in config.texture_output_definitions:
        if not output_def.enabled:
            continue
        # 收集此输出需要的逻辑源
        needed_sources = set()
        for ch_def in output_def.channels.values():
            if ch_def.source:  # 有 from 字段（非纯常量）
                needed_sources.add(ch_def.source)
        # 检查每个源是否已映射（或有 constant 兜底）
        for source in needed_sources:
            if source not in match_result.mapping:
                # 检查是否所有引用此 source 的通道都有 constant 兜底
                all_have_fallback = all(
                    ch_def.constant is not None
                    for ch_def in output_def.channels.values()
                    if ch_def.source == source
                )
                if output_def.allow_missing and all_have_fallback:
                    continue  # allow_missing + constant 兜底 = 可接受
                if source not in missing_slots:
                    missing_slots.append(source)

    failure = None
    if missing_slots:
        failure = CheckFailure(
            check_name="texture_mapping",
            reason=f"以下逻辑位未匹配到贴图: {', '.join(missing_slots)}",
            details={
                "missing_slots": missing_slots,
                "orphans": match_result.orphans,
                "ambiguous": match_result.ambiguous_slots,
            },
        )
    elif match_result.orphans:
        failure = CheckFailure(
            check_name="texture_mapping",
            reason=f"存在 {len(match_result.orphans)} 个孤儿贴图未被规则匹配",
            details={"orphans": match_result.orphans},
        )

    return match_result, failure


def run_check_chain(
    asset_names: List[str],
    texture_files: List[str],
    config: PluginConfig,
    mesh_filter: Optional[Callable[[str], bool]] = None,
    material_exists_fn: Optional[Callable[[str], bool]] = None,
) -> CheckResult:
    """执行完整检查链（FR3）。

    Args:
        asset_names: 隔离区中的资产名列表。
        texture_files: 贴图文件路径列表。
        config: 当前 Profile 配置。
        mesh_filter: 可选 StaticMesh 判定回调。
        material_exists_fn: 可选材质存在性检测回调。

    Returns:
        CheckResult：检查结果。
    """
    result = CheckResult()

    # 检查 1：资产数量
    mesh_name, failure1 = check_asset_count(asset_names, mesh_filter)
    result.static_mesh = mesh_name
    if failure1:
        result.status = CheckStatus.FAILED
        result.failures.append(failure1)

    # 检查 2：主材质
    failure2 = check_master_material(
        config.default_master_material_path,
        material_exists_fn,
    )
    if failure2:
        result.status = CheckStatus.FAILED
        result.failures.append(failure2)

    # 检查 3：贴图映射
    match_res, failure3 = check_texture_mapping(texture_files, config)
    result.match_result = match_res
    if failure3:
        result.status = CheckStatus.FAILED
        result.failures.append(failure3)

    return result
