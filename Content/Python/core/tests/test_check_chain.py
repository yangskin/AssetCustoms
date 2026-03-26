"""检查链（FR3）单元测试。"""
import os
import pytest

from core.config.schema import (
    ChannelDef,
    InputConfig,
    PluginConfig,
    ProcessingConfig,
    TextureInputConfig,
    TextureInputRule,
    TextureProcessingDef,
    OutputConfig,
    MaterialOutputConfig,
)
from core.pipeline.check_chain import (
    CheckResult,
    CheckStatus,
    check_asset_count,
    check_master_material,
    check_texture_mapping,
    run_check_chain,
)


# ---------------------------------------------------------------------------
# check_asset_count
# ---------------------------------------------------------------------------

class TestCheckAssetCount:
    def test_single_mesh(self):
        mesh, failure = check_asset_count(["SM_Rock", "T_Rock_D", "M_Rock"])
        assert mesh == "SM_Rock"
        assert failure is None

    def test_no_mesh(self):
        mesh, failure = check_asset_count(["T_Rock_D", "M_Rock"])
        assert mesh is None
        assert failure is not None
        assert failure.check_name == "asset_count"

    def test_multiple_meshes(self):
        mesh, failure = check_asset_count(["SM_Rock", "SM_Rock2"])
        assert mesh == "SM_Rock"
        assert failure is not None
        assert "2" in failure.reason

    def test_custom_filter(self):
        mesh, failure = check_asset_count(
            ["MyMesh", "MyTexture"],
            mesh_filter=lambda n: n.startswith("MyMesh"),
        )
        assert mesh == "MyMesh"
        assert failure is None


# ---------------------------------------------------------------------------
# check_master_material
# ---------------------------------------------------------------------------

class TestCheckMasterMaterial:
    def test_empty_path_passes(self):
        assert check_master_material("") is None

    def test_existing_material(self):
        assert check_master_material("/Game/M_Master", lambda _: True) is None

    def test_missing_material(self):
        failure = check_master_material("/Game/M_Missing", lambda _: False)
        assert failure is not None
        assert failure.check_name == "master_material"


# ---------------------------------------------------------------------------
# check_texture_mapping
# ---------------------------------------------------------------------------

def _make_config_for_mapping(allow_missing_mro: bool = True) -> PluginConfig:
    return PluginConfig(
        input=InputConfig(
            texture=TextureInputConfig(
                match_mode="glob",
                ignore_case=True,
                rules={
                    "BaseColor": TextureInputRule(priority=10, patterns=["*_BC.*"]),
                    "Normal": TextureInputRule(priority=10, patterns=["*_N.*"]),
                    "Roughness": TextureInputRule(priority=9, patterns=["*_R.*"]),
                    "Metallic": TextureInputRule(priority=9, patterns=["*_M.*"]),
                    "AmbientOcclusion": TextureInputRule(priority=8, patterns=["*_AO.*"]),
                },
            ),
        ),
        processing=ProcessingConfig(
            texture_definitions=[
                TextureProcessingDef(
                    enabled=True, name="Diffuse", suffix="D",
                    channels={
                        "R": ChannelDef(source="BaseColor", ch="R"),
                        "G": ChannelDef(source="BaseColor", ch="G"),
                        "B": ChannelDef(source="BaseColor", ch="B"),
                        "A": ChannelDef(constant=1.0),
                    },
                ),
                TextureProcessingDef(
                    enabled=True, name="Normal", suffix="N",
                    channels={
                        "R": ChannelDef(source="Normal", ch="R"),
                        "G": ChannelDef(source="Normal", ch="G"),
                        "B": ChannelDef(source="Normal", ch="B"),
                        "A": ChannelDef(constant=1.0),
                    },
                ),
                TextureProcessingDef(
                    enabled=True, name="Packed_MRO", suffix="MRO",
                    allow_missing=allow_missing_mro,
                    channels={
                        "R": ChannelDef(source="Metallic", ch="R", constant=0.0),
                        "G": ChannelDef(source="Roughness", ch="R", constant=0.5),
                        "B": ChannelDef(source="AmbientOcclusion", ch="R", constant=1.0),
                        "A": ChannelDef(constant=1.0),
                    },
                ),
            ],
        ),
    )


class TestCheckTextureMapping:
    def test_full_mapping_passes(self, tmp_path):
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_N.png"),
            str(tmp_path / "Rock_R.png"),
            str(tmp_path / "Rock_M.png"),
            str(tmp_path / "Rock_AO.png"),
        ]
        cfg = _make_config_for_mapping()
        match_result, failure = check_texture_mapping(files, cfg)
        assert failure is None

    def test_missing_with_allow_missing(self, tmp_path):
        """MRO 缺少三个源，但 allow_missing + constant 兜底 → 通过。"""
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_N.png"),
        ]
        cfg = _make_config_for_mapping(allow_missing_mro=True)
        match_result, failure = check_texture_mapping(files, cfg)
        assert failure is None  # MRO 有 constant 兜底

    def test_missing_without_allow_missing(self, tmp_path):
        """MRO 不允许缺失 → 失败。"""
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_N.png"),
        ]
        cfg = _make_config_for_mapping(allow_missing_mro=False)
        match_result, failure = check_texture_mapping(files, cfg)
        assert failure is not None
        assert "Metallic" in failure.details["missing_slots"] or "Roughness" in failure.details["missing_slots"]

    def test_orphan_detection(self, tmp_path):
        """孤儿贴图不再导致失败，但仍被记录在 match_result.orphans 中。"""
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_N.png"),
            str(tmp_path / "Rock_Unknown.png"),
        ]
        cfg = _make_config_for_mapping()
        match_result, failure = check_texture_mapping(files, cfg)
        assert failure is None  # 孤儿不再阻断
        assert len(match_result.orphans) == 1


# ---------------------------------------------------------------------------
# run_check_chain
# ---------------------------------------------------------------------------

class TestRunCheckChain:
    def test_all_pass(self, tmp_path):
        assets = ["SM_Rock", "T_Rock_D", "M_Rock"]
        files = [
            str(tmp_path / "Rock_BC.png"),
            str(tmp_path / "Rock_N.png"),
        ]
        cfg = _make_config_for_mapping()
        cfg.output.material.master_material_path = "/Game/M_Master"
        result = run_check_chain(
            asset_names=assets,
            texture_files=files,
            config=cfg,
            material_exists_fn=lambda _: True,
        )
        assert result.passed
        assert result.static_mesh == "SM_Rock"

    def test_no_mesh_fails(self, tmp_path):
        files = [str(tmp_path / "Rock_BC.png"), str(tmp_path / "Rock_N.png")]
        cfg = _make_config_for_mapping()
        result = run_check_chain(
            asset_names=["T_Rock_D"],
            texture_files=files,
            config=cfg,
        )
        assert not result.passed
        assert any(f.check_name == "asset_count" for f in result.failures)

    def test_missing_material_fails(self, tmp_path):
        files = [str(tmp_path / "Rock_BC.png"), str(tmp_path / "Rock_N.png")]
        cfg = _make_config_for_mapping()
        cfg.output.material.master_material_path = "/Game/M_Missing"
        result = run_check_chain(
            asset_names=["SM_Rock"],
            texture_files=files,
            config=cfg,
            material_exists_fn=lambda _: False,
        )
        assert not result.passed
        assert any(f.check_name == "master_material" for f in result.failures)

    def test_empty_material_path_skips(self, tmp_path):
        files = [str(tmp_path / "Rock_BC.png"), str(tmp_path / "Rock_N.png")]
        cfg = _make_config_for_mapping()
        cfg.output.material.master_material_path = ""
        result = run_check_chain(
            asset_names=["SM_Rock"],
            texture_files=files,
            config=cfg,
        )
        # 材质检查通过（空路径跳过），但可能有贴图映射的 orphan 问题
        assert not any(f.check_name == "master_material" for f in result.failures)
