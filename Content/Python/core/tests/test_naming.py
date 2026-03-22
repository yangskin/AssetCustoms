"""名称解析器单元测试。"""
import pytest

from core.config.schema import AssetNamingTemplate, PluginConfig, TextureOutputDef
from core.naming import (
    ResolvedNames,
    compute_isolation_path,
    extract_base_name,
    resolve_conflict,
    resolve_names,
    _expand_template,
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
            target_path_template="/Game/Assets/{Category}/{Name}",
            asset_naming_template=AssetNamingTemplate(
                static_mesh="SM_{Name}",
                material_instance="MI_{Name}",
                texture="T_{Name}_{Suffix}",
            ),
            texture_output_definitions=[
                TextureOutputDef(enabled=True, suffix="D"),
                TextureOutputDef(enabled=True, suffix="N"),
                TextureOutputDef(enabled=False, suffix="H"),  # disabled
            ],
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

    def test_custom_current_path(self):
        cfg = self._make_config()
        names = resolve_names(cfg, "Chair", "Prop", "/Game/Environment")
        assert names.isolation_path == "/Game/Environment/_temp_Chair"

    def test_character_config(self):
        cfg = PluginConfig(
            target_path_template="/Game/Characters/{Name}",
            asset_naming_template=AssetNamingTemplate(
                static_mesh="SK_{Name}",
                material_instance="MI_{Name}_Char",
                texture="T_{Name}_{Suffix}",
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
