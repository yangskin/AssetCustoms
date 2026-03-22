"""名称解析与路径模板引擎。

职责：
- 展开 {Name}/{Category}/{Suffix} 等占位符
- 根据 asset_naming_template 生成 UE 资产名
- 根据 target_path_template 生成最终落地路径
- 根据 conflict_policy 处理命名冲突
- 计算隔离区路径
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from core.config.schema import AssetNamingTemplate, PluginConfig


@dataclass
class ResolvedNames:
    """解析后的名称集合。"""
    base_name: str                    # 原始基础名（如 "MyRock"）
    category: str                     # Profile 类别（如 "Prop"）
    static_mesh: str                  # SM_MyRock
    material_instance: str            # MI_MyRock
    texture_names: Dict[str, str]     # suffix -> T_MyRock_D, T_MyRock_N ...
    target_path: str                  # /Game/Assets/Prop/MyRock
    isolation_path: str               # {current_path}/_temp_MyRock


def _expand_template(template: str, variables: Dict[str, str]) -> str:
    """展开 {Key} 占位符，未匹配的保持原样。"""
    def replacer(m: re.Match) -> str:
        key = m.group(1)
        return variables.get(key, m.group(0))
    return re.sub(r"\{(\w+)\}", replacer, template)


def resolve_names(
    config: PluginConfig,
    base_name: str,
    category: str,
    current_path: str = "/Game",
    suffixes: Optional[list[str]] = None,
) -> ResolvedNames:
    """根据配置解析所有资产名称和路径。

    Args:
        config: 加载后的 PluginConfig。
        base_name: 资产基础名（通常取自 FBX 文件名，去掉扩展名）。
        category: Profile 类别（通常取自 Profile 文件名，如 "Prop"）。
        current_path: 当前 Content Browser 路径。
        suffixes: 贴图后缀列表（如 ["D", "N", "MRO"]），不传则从 output definitions 提取。
    """
    variables = {"Name": base_name, "Category": category}
    ant = config.asset_naming_template

    sm_name = _expand_template(ant.static_mesh, variables)
    mi_name = _expand_template(ant.material_instance, variables)

    if suffixes is None:
        suffixes = [d.suffix for d in config.texture_output_definitions if d.enabled and d.suffix]

    tex_names: Dict[str, str] = {}
    for suffix in suffixes:
        tex_vars = {**variables, "Suffix": suffix}
        tex_names[suffix] = _expand_template(ant.texture, tex_vars)

    target_path = _expand_template(config.target_path_template, variables)
    isolation_path = f"{current_path}/_temp_{base_name}"

    return ResolvedNames(
        base_name=base_name,
        category=category,
        static_mesh=sm_name,
        material_instance=mi_name,
        texture_names=tex_names,
        target_path=target_path,
        isolation_path=isolation_path,
    )


def resolve_conflict(
    desired_name: str,
    policy: str,
    exists_fn: Callable[[str], bool],
) -> Optional[str]:
    """根据冲突策略解析最终名称。

    Args:
        desired_name: 期望的资产路径/名称。
        policy: "overwrite" | "skip" | "version"。
        exists_fn: 检测名称是否已存在的回调函数。

    Returns:
        最终名称。policy="skip" 且已存在时返回 None。
    """
    if not exists_fn(desired_name):
        return desired_name

    if policy == "overwrite":
        return desired_name
    elif policy == "skip":
        return None
    elif policy == "version":
        # 自动追加 _001, _002, ...
        for i in range(1, 1000):
            versioned = f"{desired_name}_{i:03d}"
            if not exists_fn(versioned):
                return versioned
        return f"{desired_name}_999"
    else:
        return desired_name


def compute_isolation_path(
    current_path: str,
    base_name: str,
    fallback_path: str = "/Game/AIGC_Dropoff",
) -> str:
    """计算隔离区路径。

    根据 FR2.3：Isolation_Path = {Current_Path}/_temp_{Base_Name}/
    Current_Path 无效则使用 fallback。
    """
    if not current_path or not current_path.startswith("/Game"):
        current_path = fallback_path
    return f"{current_path}/_temp_{base_name}"


def extract_base_name(fbx_path: str) -> str:
    """从 FBX 文件路径提取基础名（不含扩展名）。"""
    return os.path.splitext(os.path.basename(fbx_path))[0]
