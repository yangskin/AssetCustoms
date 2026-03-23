"""贴图匹配引擎单元测试。"""
import os
import tempfile
import pytest

from core.config.schema import TextureInputRule, TextureInputConfig
from core.textures.matcher import (
    MatchResult,
    discover_texture_files,
    match_textures,
    _match_glob,
    _match_regex,
)


# ---------------------------------------------------------------------------
# glob 匹配
# ---------------------------------------------------------------------------

class TestGlobMatch:
    def test_suffix_match(self):
        assert _match_glob("Rock_BC.png", "*_BC.*", True)

    def test_suffix_case_insensitive(self):
        assert _match_glob("rock_bc.png", "*_BC.*", True)

    def test_suffix_case_sensitive_fail(self):
        assert not _match_glob("rock_bc.png", "*_BC.*", False)

    def test_separator_match(self):
        assert _match_glob("Rock_N_2k.png", "*_N_*", True)

    def test_no_match(self):
        assert not _match_glob("Rock_Diffuse.png", "*_N.*", True)


# ---------------------------------------------------------------------------
# regex 匹配
# ---------------------------------------------------------------------------

class TestRegexMatch:
    def test_basic_regex(self):
        assert _match_regex("Rock_BaseColor.png", r"_BaseColor\.", True)

    def test_case_insensitive(self):
        assert _match_regex("rock_basecolor.png", r"_BaseColor\.", True)

    def test_case_sensitive_fail(self):
        assert not _match_regex("rock_basecolor.png", r"_BaseColor\.", False)


# ---------------------------------------------------------------------------
# 文件发现
# ---------------------------------------------------------------------------

class TestDiscoverTextureFiles:
    def test_find_files_in_dir(self, tmp_path):
        # 创建测试文件
        (tmp_path / "Rock_BC.png").write_bytes(b"")
        (tmp_path / "Rock_N.tga").write_bytes(b"")
        (tmp_path / "Rock_Model.fbx").write_bytes(b"")  # 不应被选中
        (tmp_path / "readme.txt").write_bytes(b"")        # 不应被选中

        files = discover_texture_files(
            search_roots=[str(tmp_path)],
            extensions=[".png", ".tga"],
            drop_dir=str(tmp_path),
        )
        basenames = sorted(os.path.basename(f) for f in files)
        assert basenames == ["Rock_BC.png", "Rock_N.tga"]

    def test_drop_dir_placeholder(self, tmp_path):
        sub = tmp_path / "Textures"
        sub.mkdir()
        (sub / "Rock_R.png").write_bytes(b"")

        files = discover_texture_files(
            search_roots=["{DropDir}/Textures"],
            extensions=[".png"],
            drop_dir=str(tmp_path),
        )
        assert len(files) == 1
        assert "Rock_R.png" in os.path.basename(files[0])

    def test_nonexistent_dir(self):
        files = discover_texture_files(
            search_roots=["/nonexistent/path"],
            extensions=[".png"],
        )
        assert files == []

    def test_dedup(self, tmp_path):
        (tmp_path / "Rock_BC.png").write_bytes(b"")
        # 同一目录出现两次
        files = discover_texture_files(
            search_roots=[str(tmp_path), str(tmp_path)],
            extensions=[".png"],
        )
        assert len(files) == 1

    def test_glob_search_root(self, tmp_path):
        """search_root 含 glob 通配符时应展开匹配目录。"""
        fbm = tmp_path / "model_abc.fbm"
        fbm.mkdir()
        (fbm / "tex_basecolor.png").write_bytes(b"")
        (fbm / "tex_normal.png").write_bytes(b"")
        # 另一个不相关目录
        (tmp_path / "other").mkdir()
        (tmp_path / "other" / "noise.png").write_bytes(b"")

        files = discover_texture_files(
            search_roots=[str(tmp_path) + "/*.fbm"],
            extensions=[".png"],
        )
        basenames = sorted(os.path.basename(f) for f in files)
        assert basenames == ["tex_basecolor.png", "tex_normal.png"]

    def test_glob_no_match(self, tmp_path):
        """glob 模式无匹配时返回空列表。"""
        files = discover_texture_files(
            search_roots=[str(tmp_path) + "/*.fbm"],
            extensions=[".png"],
        )
        assert files == []


# ---------------------------------------------------------------------------
# 贴图匹配
# ---------------------------------------------------------------------------

def _make_rules(**kwargs) -> TextureInputConfig:
    defaults = dict(
        match_mode="glob",
        ignore_case=True,
        extensions=[".png", ".tga"],
        search_roots=[],
        rules={
            "BaseColor": TextureInputRule(priority=10, patterns=["*_BC.*", "*_BaseColor.*"]),
            "Normal": TextureInputRule(priority=10, patterns=["*_N.*", "*_Normal.*"]),
            "Roughness": TextureInputRule(priority=9, patterns=["*_R.*", "*_Rough.*"]),
            "Metallic": TextureInputRule(priority=9, patterns=["*_M.*", "*_Metal.*"]),
            "AmbientOcclusion": TextureInputRule(priority=8, patterns=["*_AO.*"]),
        },
    )
    defaults.update(kwargs)
    return TextureInputConfig(**defaults)


class TestMatchTextures:
    def test_full_mapping(self, tmp_path):
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_N.png"),
            str(tmp_path / "Rock_R.png"),
            str(tmp_path / "Rock_M.png"),
            str(tmp_path / "Rock_AO.png"),
        ]
        rules = _make_rules()
        result = match_textures(files, rules)
        assert len(result.mapping) == 5
        assert result.orphans == []
        assert result.ambiguous_slots == []
        assert result.unmapped_slots == []

    def test_orphan_detection(self, tmp_path):
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_Unknown.png"),
        ]
        rules = _make_rules()
        result = match_textures(files, rules)
        assert "BaseColor" in result.mapping
        assert len(result.orphans) == 1
        assert "Rock_Unknown.png" in os.path.basename(result.orphans[0])

    def test_unmapped_slots(self, tmp_path):
        files = [str(tmp_path / "Rock_BC.png")]
        rules = _make_rules()
        result = match_textures(files, rules)
        assert "BaseColor" in result.mapping
        assert "Normal" in result.unmapped_slots
        assert "Roughness" in result.unmapped_slots

    def test_ambiguous_resolution_by_priority(self, tmp_path):
        """同一 slot，多个文件命中 → 取第一个命中。"""
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_BaseColor.png"),
        ]
        rules = _make_rules()
        result = match_textures(files, rules)
        assert "BaseColor" in result.mapping
        assert "BaseColor" in result.ambiguous_slots

    def test_regex_mode(self, tmp_path):
        files = [str(tmp_path / "Rock_BaseColor.png")]
        rules = _make_rules(
            match_mode="regex",
            rules={
                "BaseColor": TextureInputRule(priority=10, patterns=[r"_BaseColor\."]),
            },
        )
        result = match_textures(files, rules)
        assert "BaseColor" in result.mapping

    def test_empty_files(self):
        rules = _make_rules()
        result = match_textures([], rules)
        assert result.mapping == {}
        assert len(result.unmapped_slots) == 5
