"""名称解析器单元测试。"""
import pytest

from core.config.schema import (
    NamingConfig, SubdirectoriesConfig, PluginConfig, TextureProcessingDef,
    OutputConfig, ProcessingConfig,
)
from core.naming import (
    ResolvedNames,
    compute_isolation_path,
    extract_base_name,
    resolve_conflict,
    resolve_names,
    _expand_template,
    _is_readable_name,
    _strip_known_prefix,
)


class TestExpandTemplate:
    def test_basic(self):
        assert _expand_template("SM_{Name}", {"Name": "Rock"}) == "SM_Rock"

    def test_multiple(self):
        result = _expand_template("/Game/{Category}/{Name}", {"Name": "Rock", "Category": "Prop"})
        assert result == "/Game/Prop/Rock"

    def test_missing_key_preserved(self):
        result = _expand_template("T_{Name}_{Suffix}", {"Name": "Rock"})
        assert result == "T_Rock_{Suffix}"


class TestResolveNames:
    def _make_config(self) -> PluginConfig:
        return PluginConfig(
            output=OutputConfig(
                target_path_template="/Game/Assets/{Category}/{Name}",
                naming=NamingConfig(
                    static_mesh="SM_{Name}",
                    material_instance="MI_{Name}",
                    texture="T_{Name}_{Suffix}",
                ),
            ),
            processing=ProcessingConfig(
                texture_definitions=[
                    TextureProcessingDef(enabled=True, suffix="D"),
                    TextureProcessingDef(enabled=True, suffix="N"),
                    TextureProcessingDef(enabled=False, suffix="H"),  # disabled
                ],
            ),
        )

    def test_basic_resolution(self):
        cfg = self._make_config()
        names = resolve_names(cfg, "MyRock", "Prop")
        assert names.static_mesh == "SM_MyRock"
        assert names.material_instance == "MI_MyRock"
        assert names.target_path == "/Game/Assets/Prop/MyRock"
        assert names.isolation_path == "/Game/_temp_MyRock"
        assert "D" in names.texture_names
        assert "N" in names.texture_names
        assert "H" not in names.texture_names  # disabled
        assert names.texture_names["D"] == "T_MyRock_D"
        # 默认无子目录 → 全部在 target_path 下
        assert names.sm_path == "/Game/Assets/Prop/MyRock/SM_MyRock"
        assert names.mi_path == "/Game/Assets/Prop/MyRock/MI_MyRock"
        assert names.texture_base_path == "/Game/Assets/Prop/MyRock"

    def test_subdirectories(self):
        cfg = self._make_config()
        cfg.output.subdirectories = SubdirectoriesConfig(
            static_mesh="",
            material_instance="Materials",
            texture="Textures",
        )
        names = resolve_names(cfg, "MyRock", "Prop")
        assert names.sm_path == "/Game/Assets/Prop/MyRock/SM_MyRock"
        assert names.mi_path == "/Game/Assets/Prop/MyRock/Materials/MI_MyRock"
        assert names.texture_base_path == "/Game/Assets/Prop/MyRock/Textures"

    def test_subdirectories_all_empty(self):
        cfg = self._make_config()
        cfg.output.subdirectories = SubdirectoriesConfig(
            static_mesh="", material_instance="", texture="",
        )
        names = resolve_names(cfg, "Box", "Prop")
        assert names.sm_path == "/Game/Assets/Prop/Box/SM_Box"
        assert names.mi_path == "/Game/Assets/Prop/Box/MI_Box"
        assert names.texture_base_path == "/Game/Assets/Prop/Box"

    def test_empty_template_fallback_to_current_path(self):
        """target_path_template 为空时应 fallback 到 current_path。"""
        cfg = self._make_config()
        cfg.output.target_path_template = ""
        names = resolve_names(cfg, "Lamp", "Prop", "/Game/MyProject/Props")
        assert names.target_path == "/Game/MyProject/Props"
        assert names.sm_path == "/Game/MyProject/Props/SM_Lamp"
        assert names.mi_path == "/Game/MyProject/Props/MI_Lamp"
        assert names.texture_base_path == "/Game/MyProject/Props"

    def test_custom_current_path(self):
        cfg = self._make_config()
        names = resolve_names(cfg, "Chair", "Prop", "/Game/Environment")
        assert names.isolation_path == "/Game/Environment/_temp_Chair"

    def test_character_config(self):
        cfg = PluginConfig(
            output=OutputConfig(
                target_path_template="/Game/Characters/{Name}",
                naming=NamingConfig(
                    static_mesh="SK_{Name}",
                    material_instance="MI_{Name}_Char",
                    texture="T_{Name}_{Suffix}",
                ),
            ),
        )
        names = resolve_names(cfg, "Hero", "Character", suffixes=["D", "N", "SSS"])
        assert names.static_mesh == "SK_Hero"
        assert names.material_instance == "MI_Hero_Char"
        assert names.target_path == "/Game/Characters/Hero"
        assert names.texture_names["SSS"] == "T_Hero_SSS"


class TestResolveConflict:
    def test_no_conflict(self):
        result = resolve_conflict("path/Asset", "version", lambda _: False)
        assert result == "path/Asset"

    def test_overwrite(self):
        result = resolve_conflict("path/Asset", "overwrite", lambda _: True)
        assert result == "path/Asset"

    def test_skip(self):
        result = resolve_conflict("path/Asset", "skip", lambda _: True)
        assert result is None

    def test_version(self):
        existing = {"path/Asset"}
        def exists(name):
            return name in existing
        result = resolve_conflict("path/Asset", "version", exists)
        assert result == "path/Asset_001"

    def test_version_increments(self):
        existing = {"path/Asset", "path/Asset_001", "path/Asset_002"}
        def exists(name):
            return name in existing
        result = resolve_conflict("path/Asset", "version", exists)
        assert result == "path/Asset_003"


class TestComputeIsolationPath:
    def test_valid_path(self):
        result = compute_isolation_path("/Game/Environment", "Rock")
        assert result == "/Game/Environment/_temp_Rock"

    def test_invalid_path_uses_fallback(self):
        result = compute_isolation_path("", "Rock")
        assert result == "/Game/AIGC_Dropoff/_temp_Rock"

    def test_non_game_path_uses_fallback(self):
        result = compute_isolation_path("/Engine/Test", "Rock")
        assert result == "/Game/AIGC_Dropoff/_temp_Rock"

    def test_custom_fallback(self):
        result = compute_isolation_path("", "Rock", "/Game/CustomFallback")
        assert result == "/Game/CustomFallback/_temp_Rock"


class TestExtractBaseName:
    def test_fbx(self):
        assert extract_base_name("C:/Models/MyRock.fbx") == "MyRock"

    def test_nested_path(self):
        assert extract_base_name("/home/user/assets/Character_Hero.FBX") == "Character_Hero"

    def test_strip_sm_prefix(self):
        assert extract_base_name("C:/Models/SM_HeroSword.fbx") == "HeroSword"

    def test_strip_sk_prefix(self):
        assert extract_base_name("C:/Models/SK_Monster.fbx") == "Monster"

    def test_garbled_uuid_truncated(self):
        """Tripo 等 AI 工具导出的 UUID 长文件名 → 截取前 12 字符。"""
        result = extract_base_name(
            "C:/Models/tripo_convert_07eaa50d-9af7-4391-aefb-6e4ec42ec7b1.fbx"
        )
        assert result == "tripo_conver"

    def test_garbled_short_name(self):
        """不足 12 字符的乱码名直接全用。"""
        result = extract_base_name("C:/Models/ab3f9e1c.fbx")
        assert len(result) <= 12

    def test_readable_name_not_truncated(self):
        """正常可读名称不受截断影响。"""
        assert extract_base_name("C:/Models/BeautifulChair.fbx") == "BeautifulChair"

    def test_trailing_separator_stripped(self):
        """截断后末尾的下划线/短横线被清理。"""
        # 假设文件名 12 字符处恰好是 '_'
        result = extract_base_name("C:/Models/abcdef01234_rest_of_uuid_name.fbx")
        assert not result.endswith("_")
        assert not result.endswith("-")


class TestIsReadableName:
    def test_normal_name(self):
        assert _is_readable_name("MyRock") is True

    def test_uuid_name(self):
        assert _is_readable_name("07eaa50d-9af7-4391-aefb-6e4ec42ec7b1") is False

    def test_hex_block(self):
        assert _is_readable_name("tripo_convert_07eaa50d") is False

    def test_long_name(self):
        assert _is_readable_name("A" * 41) is False

    def test_short_hex_ok(self):
        """7 位以下 hex 不触发 UUID 检测。"""
        assert _is_readable_name("abc1234") is True


class TestStripKnownPrefix:
    def test_sm_prefix(self):
        assert _strip_known_prefix("SM_Rock") == "Rock"

    def test_no_prefix(self):
        assert _strip_known_prefix("MyChair") == "MyChair"

    def test_only_first_prefix(self):
        assert _strip_known_prefix("SM_T_Weird") == "T_Weird"
