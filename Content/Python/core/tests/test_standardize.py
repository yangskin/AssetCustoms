"""标准化引擎贴图处理（FR5.1）单元测试。"""
import os
import tempfile
import pytest

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from core.config.schema import (
    ChannelDef,
    MaterialOutputConfig,
    NamingConfig,
    OutputConfig,
    PluginConfig,
    ProcessingConfig,
    TextureImportDefaults,
    TextureProcessingDef,
)
from core.pipeline.standardize import (
    ProcessedTexture,
    StandardizeResult,
    process_textures,
    _apply_flip_green,
    _resize_image,
    _load_source_images,
)


pytestmark = pytest.mark.skipif(not HAS_PILLOW, reason="Pillow not installed")


def _make_test_image(width=64, height=64, color=(128, 64, 32, 255)):
    """创建测试用 RGBA 图像。"""
    return Image.new("RGBA", (width, height), color)


def _save_test_image(path, width=64, height=64, color=(128, 64, 32, 255)):
    """保存测试图像到磁盘。"""
    img = _make_test_image(width, height, color)
    img.save(path)
    return path


class TestFlipGreen:
    def test_flip_green_inverts_g_channel(self):
        img = _make_test_image(4, 4, (100, 200, 50, 255))
        flipped = _apply_flip_green(img)
        r, g, b, a = flipped.split()
        # G 应该被反转: 200 -> 55
        assert list(g.getdata())[0] == 55
        # R, B, A 不变
        assert list(r.getdata())[0] == 100
        assert list(b.getdata())[0] == 50
        assert list(a.getdata())[0] == 255


class TestResizeImage:
    def test_no_resize(self):
        img = _make_test_image(64, 64)
        result = _resize_image(img, None)
        assert result.size == (64, 64)

    def test_resize(self):
        img = _make_test_image(64, 64)
        result = _resize_image(img, {"width": 32, "height": 32})
        assert result.size == (32, 32)

    def test_same_size_noop(self):
        img = _make_test_image(64, 64)
        result = _resize_image(img, {"width": 64, "height": 64})
        assert result is img  # 同一对象，未创建新图


class TestLoadSourceImages:
    def test_load_valid(self, tmp_path):
        path = str(tmp_path / "test.png")
        _save_test_image(path)
        sources = _load_source_images({"BaseColor": path})
        assert "BaseColor" in sources
        assert sources["BaseColor"].mode == "RGBA"

    def test_missing_file_skipped(self, tmp_path):
        sources = _load_source_images({"BaseColor": str(tmp_path / "nonexistent.png")})
        assert "BaseColor" not in sources


class TestProcessTextures:
    def _make_config(self) -> PluginConfig:
        return PluginConfig(
            processing=ProcessingConfig(
                texture_definitions=[
                    TextureProcessingDef(
                        enabled=True,
                        name="Diffuse",
                        suffix="D",
                        srgb=True,
                        format="PNG",
                        bit_depth=8,
                        channels={
                            "R": ChannelDef(source="BaseColor", ch="R"),
                            "G": ChannelDef(source="BaseColor", ch="G"),
                            "B": ChannelDef(source="BaseColor", ch="B"),
                            "A": ChannelDef(constant=1.0),
                        },
                    ),
                    TextureProcessingDef(
                        enabled=True,
                        name="Normal",
                        suffix="N",
                        srgb=False,
                        flip_green=True,
                        format="PNG",
                        bit_depth=8,
                        channels={
                            "R": ChannelDef(source="Normal", ch="R"),
                            "G": ChannelDef(source="Normal", ch="G"),
                            "B": ChannelDef(source="Normal", ch="B"),
                            "A": ChannelDef(constant=1.0),
                        },
                    ),
                    TextureProcessingDef(
                        enabled=True,
                        name="Packed_MRO",
                        suffix="MRO",
                        srgb=False,
                        allow_missing=True,
                        format="PNG",
                        bit_depth=8,
                        channels={
                            "R": ChannelDef(source="Metallic", ch="R", constant=0.0),
                            "G": ChannelDef(source="Roughness", ch="R", constant=0.5),
                            "B": ChannelDef(source="AmbientOcclusion", ch="R", constant=1.0),
                            "A": ChannelDef(constant=1.0),
                        },
                    ),
                ],
            ),
            output=OutputConfig(
                naming=NamingConfig(texture="T_{Name}_{Suffix}"),
                material=MaterialOutputConfig(
                    parameter_bindings={
                        "D": "BaseColor_Texture",
                        "N": "Normal_Texture",
                        "MRO": "Packed_Texture",
                    },
                ),
                texture_import_defaults=TextureImportDefaults(
                    compression="TC_Default",
                    lod_group="TEXTUREGROUP_World",
                ),
                texture_import_overrides={
                    "N": {"compression": "TC_Normalmap"},
                    "MRO": {"compression": "TC_Masks"},
                },
            ),
        )

    def test_full_pipeline(self, tmp_path):
        # 创建源贴图
        bc_path = _save_test_image(str(tmp_path / "Rock_BC.png"), color=(200, 100, 50, 255))
        n_path = _save_test_image(str(tmp_path / "Rock_N.png"), color=(128, 128, 255, 255))

        mapping = {"BaseColor": bc_path, "Normal": n_path}

        with tempfile.TemporaryDirectory() as out_dir:
            cfg = self._make_config()
            result = process_textures(cfg, mapping, out_dir, "Rock", "Prop")

            assert result.success
            assert len(result.textures) == 3  # Diffuse + Normal + MRO

            # 验证文件已保存
            for tex in result.textures:
                assert os.path.exists(tex.file_path)
                assert tex.material_parameter

            # 验证 Diffuse
            diffuse = next(t for t in result.textures if t.suffix == "D")
            assert "T_Rock_D" in os.path.basename(diffuse.file_path)
            assert diffuse.srgb is True

            # 验证 Normal 有 flip_green
            normal = next(t for t in result.textures if t.suffix == "N")
            assert "T_Rock_N" in os.path.basename(normal.file_path)
            # 检查 G 通道确实被反转
            normal_img = Image.open(normal.file_path)
            _, g, _, _ = normal_img.split()
            # 原始 G=128, flip 后应为 127
            assert abs(list(g.getdata())[0] - 127) <= 1

            # 验证 MRO（使用 constant 兜底）
            mro = next(t for t in result.textures if t.suffix == "MRO")
            mro_img = Image.open(mro.file_path)
            r, g, b, a = mro_img.split()
            # Metallic constant=0.0 → R≈0
            assert list(r.getdata())[0] <= 1
            # Roughness constant=0.5 → G≈128
            assert abs(list(g.getdata())[0] - 128) <= 1
            # AO constant=1.0 → B=255
            assert list(b.getdata())[0] >= 254

    def test_disabled_output_skipped(self, tmp_path):
        cfg = self._make_config()
        cfg.processing.texture_definitions[0].enabled = False  # 禁用 Diffuse

        bc_path = _save_test_image(str(tmp_path / "Rock_BC.png"))
        n_path = _save_test_image(str(tmp_path / "Rock_N.png"))

        with tempfile.TemporaryDirectory() as out_dir:
            result = process_textures(cfg, {"BaseColor": bc_path, "Normal": n_path}, out_dir, "Rock")
            assert result.success
            assert len(result.textures) == 2  # Normal + MRO

    def test_import_settings_collected(self, tmp_path):
        cfg = self._make_config()
        bc_path = _save_test_image(str(tmp_path / "Rock_BC.png"))

        with tempfile.TemporaryDirectory() as out_dir:
            result = process_textures(cfg, {"BaseColor": bc_path}, out_dir, "Rock")
            diffuse = next(t for t in result.textures if t.suffix == "D")
            assert diffuse.import_settings["compression"] == "TC_Default"
            assert diffuse.import_settings["lod_group"] == "TEXTUREGROUP_World"
