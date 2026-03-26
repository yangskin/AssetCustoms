# 开发与测试（Core - 纯 Python）

核心功能与算法（位于 `Content/Python/core`）不依赖 Unreal，可在本地以测试驱动开发（TDD）。

## 目录
- 代码：`Content/Python/core`
- 测试：`Content/Python/core/tests`

## 创建并使用虚拟环境（PowerShell）

```powershell
# 进入仓库根目录
cd c:\Work\Unreal\ToolTest\Plugins\AssetCustoms

# 创建虚拟环境（首次执行）
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装开发/测试依赖（不影响 Unreal 环境）
python -m pip install -r requirements-dev.txt
```

## 运行测试

```powershell
# 从仓库根启动全部核心测试
python .\run_tests.py
```

若只运行某个用例，可直接使用 pytest 语法：

```powershell
# 运行单文件
python -m pytest .\Content\Python\core\tests\test_layer_merge.py -q

# 运行并筛选关键字
python -m pytest .\Content\Python\core\tests -k multiply -q
```

## 说明
- `core.textures.layer_merge`：优先使用 numpy 加速；若环境无 numpy，将自动回退到较慢的 Pillow 叠加路径。测试中覆盖了两种路径（通过 monkeypatch 将 `np` 置为 None）。
- 配置解析：`core.config.loader` 可从 dict 或 .json 载入，合并默认值并解析 `BlendMode`；测试包含最小验证。

## 常见问题
- 若提示 `pytest 未安装`：请确认已执行依赖安装命令。
- 若导入路径报错：测试已自动将 `Content/Python` 加到 `sys.path`，通常无需手动设置。

## 测试状态（2026-03-26）
- 环境：Windows / Python 3.11.8 / pytest 8.4.2
- AssetCustoms Core：103 passed, 20 skipped（共 123 项用例）
- AssetCustoms 全量（含 M7 UE 侧）：56 passed
- SPsync（含 M7-M9 SP 侧 + Round-Trip Sync + Texture Size Control + Resolution Authority）：191 passed
- Doctest：48 passed
- 跳过原因：20 项 `test_standardize` 依赖 Pillow（测试环境未安装时自动跳过）
- 覆盖范围：
  - 配置解析（JSONC / Schema v1.1 / loader）
  - 贴图引擎（layer_merge / channel_pack / matcher）
  - 命名解析（resolve_names / extract_base_name / conflict / isolation_path）
  - 检查链（check_chain: asset_count / master_material / texture_mapping）
  - 标准化引擎（process_textures / flip_green / resize）
  - 分诊 UI（TriageWindow / TriageDecision / 回调）
  - M7 SP Bridge（sp_remote: base64/HTTP mock，sp_bridge: JSON schema/序列化/数据包）
  - M7 SP Receive（JSON 解析/校验、导出配置生成、通道映射、Grayscale Filter）
  - M7 Round-Trip Sync（metadata 构建、roundtrip 导出配置、refresh list、srcMapName 映射）
  - M8 贴图尺寸控制（max_resolution int 解析、sizeLog2 计算、SP 分辨率 Clamp）
  - M9 分辨率权威分离（texture_size 序列化、update_texture_sizes_from_exports、Clamp [128, 4096]）
