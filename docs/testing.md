# 开发与测试（Core - 纯 Python）

核心功能与算法（位于 `Content/Python/core`）不依赖 Unreal，可在本地以测试驱动开发（TDD）。

## 目录
- 代码：`Content/Python/core`
- 测试：`Content/Python/core/tests`

## 依赖安装（PowerShell）

```powershell
# 进入仓库根目录
cd c:\Work\Unreal\ToolTest\Plugins\AssetCustoms

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
