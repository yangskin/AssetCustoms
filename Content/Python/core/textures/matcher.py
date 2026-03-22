"""贴图文件匹配引擎：根据 texture_input_rules 将磁盘文件映射到逻辑位。

核心职责：
- 扫描指定目录（search_roots）中符合 extensions 的文件
- 按 rules 中的 glob/regex 模式 + priority 将文件匹配到逻辑位
- 返回 MatchResult：完整映射 + 未映射文件（孤儿）+ 歧义项
"""
from __future__ import annotations

import fnmatch
import glob
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from core.config.schema import TextureInputRules


@dataclass
class MatchHit:
    """单次匹配命中。"""
    slot: str          # 逻辑位名（如 "BaseColor"）
    pattern: str       # 命中的具体模式
    priority: int      # 规则优先级
    file_path: str     # 匹配到的文件路径


@dataclass
class MatchResult:
    """匹配引擎的完整输出。"""
    # 逻辑位 -> 最终选中的文件路径
    mapping: Dict[str, str] = field(default_factory=dict)
    # 逻辑位 -> 所有候选命中（用于分诊 UI 展示歧义）
    candidates: Dict[str, List[MatchHit]] = field(default_factory=dict)
    # 未映射到任何逻辑位的文件（孤儿）
    orphans: List[str] = field(default_factory=list)
    # 歧义位：一个逻辑位有多个候选文件
    ambiguous_slots: List[str] = field(default_factory=list)
    # 未映射位：配置中有规则但没有匹配到文件
    unmapped_slots: List[str] = field(default_factory=list)


def discover_texture_files(
    search_roots: List[str],
    extensions: List[str],
    drop_dir: str = "",
) -> List[str]:
    """扫描 search_roots 中符合 extensions 的贴图文件。

    Args:
        search_roots: 搜索根目录列表，支持 {DropDir} 占位符。
        extensions: 允许的文件扩展名（如 [".png", ".tga"]）。
        drop_dir: FBX 所在目录，用于替换 {DropDir}。

    Returns:
        去重后的文件绝对路径列表。
    """
    ext_set = {e.lower() for e in extensions}
    seen: Set[str] = set()
    result: List[str] = []

    for root_template in search_roots:
        root = root_template.replace("{DropDir}", drop_dir)
        # 支持 glob 通配符（如 {DropDir}/*.fbm）
        if "*" in root or "?" in root:
            matched_dirs = [d for d in glob.glob(root) if os.path.isdir(d)]
        elif os.path.isdir(root):
            matched_dirs = [root]
        else:
            matched_dirs = []
        for root_dir in matched_dirs:
            for entry in os.listdir(root_dir):
                full = os.path.join(root_dir, entry)
                if not os.path.isfile(full):
                    continue
                _, ext = os.path.splitext(entry)
                if ext.lower() not in ext_set:
                    continue
                norm = os.path.normcase(os.path.abspath(full))
                if norm not in seen:
                    seen.add(norm)
                    result.append(full)
    return result


def _match_glob(filename: str, pattern: str, ignore_case: bool) -> bool:
    """glob 模式匹配（仅文件名，不含路径）。"""
    if ignore_case:
        return fnmatch.fnmatch(filename.lower(), pattern.lower())
    # 使用 fnmatchcase 确保大小写敏感（fnmatch 在 Windows 上默认不区分大小写）
    return fnmatch.fnmatchcase(filename, pattern)


def _match_regex(filename: str, pattern: str, ignore_case: bool) -> bool:
    """正则模式匹配（仅文件名）。"""
    flags = re.IGNORECASE if ignore_case else 0
    return re.search(pattern, filename, flags) is not None


def match_textures(
    files: List[str],
    rules: TextureInputRules,
) -> MatchResult:
    """将文件列表按规则匹配到逻辑位。

    Args:
        files: 贴图文件路径列表。
        rules: 来自配置的 TextureInputRules。

    Returns:
        MatchResult，包含映射、候选、孤儿、歧义和未映射信息。
    """
    match_fn = _match_regex if rules.match_mode == "regex" else _match_glob
    ignore_case = rules.ignore_case

    # slot -> [(priority, pattern, file_path)]
    slot_hits: Dict[str, List[MatchHit]] = {slot: [] for slot in rules.rules}
    # 跟踪哪些文件被匹配到了
    matched_files: Set[str] = set()

    for fpath in files:
        filename = os.path.basename(fpath)
        for slot_name, rule in rules.rules.items():
            for pattern in rule.patterns:
                if match_fn(filename, pattern, ignore_case):
                    slot_hits[slot_name].append(MatchHit(
                        slot=slot_name,
                        pattern=pattern,
                        priority=rule.priority,
                        file_path=fpath,
                    ))
                    matched_files.add(os.path.normcase(os.path.abspath(fpath)))
                    break  # 一个文件在同一 slot 内只需命中一次

    # 按 priority 降序排序每个 slot 的候选
    for slot_name in slot_hits:
        slot_hits[slot_name].sort(key=lambda h: -h.priority)

    # 构建结果
    result = MatchResult()
    result.candidates = slot_hits

    for slot_name, hits in slot_hits.items():
        if not hits:
            result.unmapped_slots.append(slot_name)
        elif len(hits) == 1:
            result.mapping[slot_name] = hits[0].file_path
        else:
            # 去重：同一文件可能因多个 pattern 命中
            unique_files = list(dict.fromkeys(h.file_path for h in hits))
            if len(unique_files) == 1:
                result.mapping[slot_name] = unique_files[0]
            else:
                # 歧义：取最高优先级的第一个
                result.mapping[slot_name] = hits[0].file_path
                result.ambiguous_slots.append(slot_name)

    # 孤儿：未被任何规则匹配的文件
    for fpath in files:
        norm = os.path.normcase(os.path.abspath(fpath))
        if norm not in matched_files:
            result.orphans.append(fpath)

    return result


def match_textures_from_disk(
    rules: TextureInputRules,
    drop_dir: str,
) -> MatchResult:
    """便捷函数：从磁盘扫描 + 匹配一步完成。"""
    files = discover_texture_files(
        search_roots=rules.search_roots,
        extensions=rules.extensions,
        drop_dir=drop_dir,
    )
    return match_textures(files, rules)
