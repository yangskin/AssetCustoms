# AssetCustoms — UE5 资产自动化插件

> 版本: V1.4（Texture Size Control + Resolution Authority） | 引擎: Unreal Engine 5.7 | 语言: Python（UE Editor Python）

AssetCustoms 是 UE 编辑器 Python 插件，定位为项目资产管线的「标准化守门员」。它将外部"数字毛坯"资产通过 TA 配置的自动化工作流实现**一键转化**，生成符合规范的生产就绪资产（命名、PBR 贴图打包、材质实例创建、导入设置）。同时支持与 Substance Painter（通过配套插件 [SPsync](#跨项目协作spsync)）的双向同步，包括一键发送、配置驱动通道映射、贴图尺寸控制和回传刷新。

> **注意**：AssetCustoms（UE 侧）与 SPsync（SP 侧）是**独立发布**的两个插件，分别安装在 UE 项目和 SP 插件目录中。

---

## 目录

- [快速开始](#快速开始)
- [部署指南](#部署指南)
- [功能概览](#功能概览)
- [配置架构：Input → Processing → Output 三段式模型](#配置架构input--processing--output-三段式模型)
- [目录结构](#目录结构)
- [开发与测试](#开发与测试)
- [文档导航](#文档导航)
- [常见问题](#常见问题)

---

## 快速开始

### 前置条件

| 项目 | 要求 |
|------|------|
| 引擎 | Unreal Engine 5.5+ （当前开发基于 5.7） |
| 系统 | Windows 10/11 64-bit |
| 插件位置 | 项目 `Plugins/AssetCustoms/` 目录下 |

### 安装步骤（3 步完成）

```
1. 将 AssetCustoms 文件夹放入项目的 Plugins/ 目录
2. 双击 deploy.bat 安装 Python 依赖
3. 启动 UE 编辑器，在 Content Browser 工具栏看到 "AssetCustoms" 下拉菜单即成功
```

---

## 部署指南

### 方式一：双击 deploy.bat（推荐）

**适用场景**：所有 Windows 用户，无需任何配置。

直接**双击** `deploy.bat`，脚本会自动：
1. 查找系统 PowerShell（`powershell` 或 `pwsh`）
2. 以 `-ExecutionPolicy Bypass` 调用 `deploy.ps1`（无需修改系统执行策略）
3. 自动检测 UE 引擎内置 Python 解释器
4. 优先从 `vendor/` 离线安装 wheel 包（无需网络）
5. 回退到 PyPI 在线安装（需网络）
6. 验证 Pillow 和 PySide6 是否可用

```
Plugins/AssetCustoms/
  deploy.bat          ← 双击此文件
  deploy.ps1          ← 实际安装逻辑（由 .bat 调用）
  vendor/             ← 离线 wheel 包
    pillow-12.1.1-cp311-cp311-win_amd64.whl
    pyside6_essentials-6.10.2-cp39-abi3-win_amd64.whl
    shiboken6-6.10.2-cp39-abi3-win_amd64.whl
```

#### 带参数运行

在命令行（cmd / PowerShell / Terminal）中执行：

```batch
:: 默认安装（离线优先）
deploy.bat

:: 强制在线安装（跳过 vendor/）
deploy.bat -Online

:: 清理已安装包后重新安装
deploy.bat -Clean

:: 指定 Python 解释器
deploy.bat -PythonExe "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
```

### 方式二：直接运行 deploy.ps1

**适用场景**：已配置 PowerShell 执行策略的开发者。

```powershell
# 在 AssetCustoms 目录下
.\deploy.ps1

# 或显式 bypass
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

### 方式三：手动 pip 安装

**适用场景**：自动脚本失败时的手动兜底。

```powershell
# 找到 UE Python 路径
$py = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"

# 从 vendor/ 离线安装
& $py -m pip install vendor\pillow-12.1.1-cp311-cp311-win_amd64.whl vendor\pyside6_essentials-6.10.2-cp39-abi3-win_amd64.whl vendor\shiboken6-6.10.2-cp39-abi3-win_amd64.whl --target Content\Python --upgrade --no-deps

# 或从 PyPI 在线安装
& $py -m pip install -r requirements.txt --target Content\Python --upgrade
```

### 验证安装

安装完成后，脚本会自动验证。也可手动检查：

```python
# 在 UE Editor 的 Python 控制台执行
from PIL import Image
print(Image.__version__)

from PySide6 import QtCore, QtWidgets
print(QtCore.qVersion())
```

### 安装目标与原理

所有依赖包安装到 `Content/Python/` 目录：
- UE 启动时自动将插件 `Content/Python/` 加入 `sys.path`
- 无需修改系统 Python 环境或 UE 引擎文件
- 各项目独立管理，互不影响

### 运行时依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| Pillow | ≥ 10.0.0 | 贴图通道编排、格式转换 |
| PySide6-Essentials | ≥ 6.5.0 | 分诊 UI、Config Editor 等 Qt 界面 |
| shiboken6 | ≥ 6.5.0 | PySide6 C++ 绑定运行时 |
| psd-tools | ≥ 1.9.0 | PSD 文件读写（Send to Photoshop 功能） |

> 离线 wheel 已内置在 `vendor/` 目录，`deploy.bat` 默认优先使用。

---

## 功能概览

### 已完成功能（V1.1）

| 模块 | 功能 | 状态 |
|------|------|------|
| **FR1** 配置系统 | JSONC Profile 扫描/加载/校验（Schema v1.1） | ✅ |
| **FR2** 智能导入 | Content Browser 下拉、文件对话框、隔离区导入 | ✅ |
| **FR2.5** 嵌入贴图管线 | FBX 内嵌贴图自动识别、三层匹配、原生处理 | ✅ |
| **FR3** 检查链 | 资产数量/材质/贴图映射完整性自动检查 | ✅ |
| **FR4** 分诊 UI | PySide6 TriageWindow，检查失败时弹出修正界面 | ✅ |
| **FR5** 标准化引擎 | 贴图处理、重命名、MIC 创建、SM→MI 绑定、清理 | ✅ |
| **M3** 质量体验 | 5s 性能预算、异常隔离、无配置 UI 禁用 | ✅ |
| **M4** 批处理 | 多 FBX 批量导入、分诊排队 | ✅ |
| Config Editor | 三页签 GUI 配置编辑器（Input/Processing/Output） | ✅ |
| 健壮性审计 | 7 项问题修复（内存泄漏、静默异常等） | ✅ |
| **M5** Config v2.0 | 三段式管线模型（Input→Processing→Output） | ✅ |
| **M6** Send to Photoshop | Content Browser 右键发送贴图到 PS，自动监控回写 | ✅ |
| **M7** Send to Substance Painter | 右键发送 SM 到 SP，Config Profile 驱动通道映射，Round-Trip 回传 | ✅ |
| **M8** 贴图尺寸控制 | `max_resolution`（int POT）全管线统一：UE 导入 → SP 项目 → SP 导出 | ✅ |
| **M9** 分辨率权威分离 | `texture_size` 来源于导出文件实际尺寸，SP 端 Clamp [128, 4096] | ✅ |

详见 [`docs/roadmap.md`](docs/roadmap.md)。

### 跨项目协作（SPsync）

AssetCustoms 的 **Send to Substance Painter** 功能与 SP 侧的 [SPsync](https://github.com/xxx/SPsync) 插件协作完成。两者**独立发布**：

| 插件 | 安装位置 | 职责 |
|------|----------|------|
| **AssetCustoms**（本插件） | UE 项目 `Plugins/AssetCustoms/` | 材质收集、FBX/贴图导出、数据包发送、贴图回传刷新 |
| **SPsync** | SP 插件目录 `...\Substance 3D Painter\python\plugins\SPsync\` | 项目创建、Layer 构建、通道映射、导出、双向同步 |

**通信方式**：
- UE→SP：HTTP POST base64(python_script) → SP Remote Scripting API（localhost:60041）
- SP→UE：Remote Execution TCP 协议（localhost:6776）

**前置条件**：
- SP 以 `--enable-remote-scripting` 参数启动
- SPsync 插件已安装并启用
- AssetCustoms `deploy.bat` 已执行

---

## 配置架构：Input → Processing → Output 三段式模型

V2.0 将 V1.1 扁平的配置重构为 **三段式管线模型**，按数据流向将关注点彻底分离：

```
┌─────────────────────────────────────────────────────────┐
│  JSONC Profile（如 Prop.jsonc / Character.jsonc）        │
├─────────┬──────────────┬────────────────────────────────┤
│  input  │  processing  │  output                        │
│─────────│──────────────│────────────────────────────────│
│ 贴图识别│ 冲突策略     │ 目标路径 / 子目录              │
│ 规则表  │ Mesh 导入设置│ 命名模板（SM/MI/贴图）         │
│ (match  │ 贴图处理定义 │ 材质绑定（suffix → MI param）  │
│  mode + │ (通道编排 +  │ 导入设置默认值                 │
│  glob/  │  format +    │ 逐贴图 import override 表格    │
│  regex) │  bit_depth)  │                                │
└─────────┴──────────────┴────────────────────────────────┘
```

### 设计意图

| 问题（V1.1） | 解决方案（V2.0） |
|--------------|------------------|
| 扁平结构导致「贴图处理定义」与「UE 导入设置」混杂 | 三段分层：input 只管识别、processing 只管处理、output 只管交付 |
| 贴图 import override 分散在各处 | 集中到 `output.texture_import_overrides`，按 suffix 统一表格管理 |
| 材质参数绑定与贴图定义耦合 | `output.material.parameter_bindings` 独立表（suffix → MI param name） |
| 命名模板位置不直观 | 全部归入 `output.naming`（static_mesh / material_instance / texture 三个模板） |

### 三段职责

- **Input**（输入阶段）：定义「从哪里来、怎么识别」。贴图规则表（match_mode + glob/regex + priority），Mesh/Material 规则预留。
- **Processing**（处理阶段）：定义「怎么加工」。冲突策略、FBX Mesh 导入参数（ADR-0003）、贴图通道编排（Pillow 管道：sources → channels → format/bit_depth/srgb/mips）。
- **Output**（输出阶段）：定义「往哪里放、叫什么名、怎么绑定」。目标路径、子目录、命名模板、母材质与参数绑定、UE 导入设置默认值与 per-suffix 覆盖。

### Config Editor UI

Config Editor GUI 严格对应三段式架构，提供 **Input / Processing / Output** 三个页签，支持中英文切换，所有配置字段均可可视化编辑并保存为 JSONC。

> 设计决策详见 [ADR-0002](docs/decisions/ADR-0002-config-v2-pipeline-model.md)。

---

## 目录结构

```
AssetCustoms/
├── AssetCustoms.uplugin        # UE 插件描述文件
├── deploy.bat                  # ★ 双击部署入口（.bat → .ps1 引导）
├── deploy.ps1                  # 依赖安装脚本（离线优先 → PyPI 回退）
├── requirements.txt            # 运行时依赖声明
├── requirements-dev.txt        # 开发/测试依赖
├── run_tests.py                # 测试启动器
├── README.md                   # 本文件
├── CONTRIBUTING.md             # 贡献指南
├── SECURITY.md                 # 安全策略
├── Content/
│   ├── Config/AssetCustoms/    # Profile 配置文件（JSONC）
│   │   ├── Prop.jsonc
│   │   └── Character.jsonc
│   └── Python/
│       ├── init_unreal.py      # UE Python 入口脚本
│       ├── core/               # 纯 Python 核心（无 UE 依赖，可独立测试）
│       │   ├── config/         # 配置解析与 Schema
│       │   ├── pipeline/       # 检查链、分诊 UI、标准化引擎
│       │   ├── textures/       # 贴图匹配与通道编排
│       │   ├── naming.py       # 命名规则与路径计算
│       │   └── tests/          # 单元测试
│       ├── unreal_integration/ # UE API 桥接层
│       └── unreal_qt/          # PySide6 Qt 集成层
│           ├── __init__.py     # QApp 管理 / tick 挂载 / widget 生命周期
│           └── dark_bar.py     # 无边框暗色标题栏
├── vendor/                     # 离线 wheel 包（随插件分发）
│   ├── pillow-*.whl
│   ├── pyside6_essentials-*.whl
│   ├── shiboken6-*.whl
│   ├── psd_tools-*.whl
│   ├── attrs-*.whl
│   ├── typing_extensions-*.whl
│   └── numpy-*.whl
├── docs/                       # 项目文档
│   ├── architecture.md         # 系统架构 / 模块边界 / 数据流
│   ├── requirements_v1.1.md    # 需求规格
│   ├── roadmap.md              # 路线图 / 里程碑
│   ├── testing.md              # 测试说明
│   └── decisions/              # 架构决策记录（ADR）
├── standards/                  # 开发规范
│   ├── coding-style.md
│   ├── review-checklist.md
│   └── commit-convention.md
└── Tests/                      # 集成/E2E 测试脚本
```

---

## 开发与测试

### 纯 Python 测试（无需 UE）

核心代码 `Content/Python/core/` 可在普通 Python 环境下测试：

```powershell
# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python run_tests.py
# 或
pytest Content/Python/core/tests/ -v --tb=short
```

### UE 编辑器内验证

1. 启动 UE 编辑器加载项目
2. 打开 Output Log（Window → Developer Tools → Output Log）
3. 筛选 `LogPython` 查看插件初始化日志
4. Content Browser 工具栏应出现 "AssetCustoms" 下拉菜单

### 开发提示

- UE 缓存已导入的 Python 模块，修改 `.py` 后需 `importlib.reload()` 或重启编辑器
- 变更公共行为时请更新文档并考虑补充 ADR
- 避免阻塞主线程的耗时操作

---

## 文档导航

| 文档 | 说明 |
|------|------|
| [`docs/roadmap.md`](docs/roadmap.md) | 路线图、里程碑与进度 |
| [`docs/architecture.md`](docs/architecture.md) | 系统架构、模块边界、数据流 |
| [`docs/requirements_v1.1.md`](docs/requirements_v1.1.md) | V1.1 详细需求规格 |
| [`docs/testing.md`](docs/testing.md) | 测试说明与环境配置 |
| [`docs/decisions/`](docs/decisions/) | 架构决策记录（ADR） |
| [`standards/coding-style.md`](standards/coding-style.md) | 编码规范（Google Python） |
| [`standards/review-checklist.md`](standards/review-checklist.md) | Code Review 检查单 |
| [`standards/commit-convention.md`](standards/commit-convention.md) | 提交规范（Conventional Commits） |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 贡献指南 |
| [`SECURITY.md`](SECURITY.md) | 安全策略 |

---

## 常见问题

### Q: 双击 deploy.bat 闪退 / 无反应？

检查 PowerShell 是否可用：在命令行输入 `powershell --version`。Windows 10+ 系统均自带 PowerShell 5.1。

### Q: 安装报错 "pip not found"？

UE 内置 Python 已包含 pip。确认 UE 引擎路径正确，或使用 `-PythonExe` 参数手动指定：
```batch
deploy.bat -PythonExe "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
```

### Q: vendor/ 里的 wheel 版本不匹配当前 Python？

wheel 文件包名中的 `cp311` 表示 Python 3.11（UE 5.7 内置版本）。如果引擎版本不同，使用在线安装：
```batch
deploy.bat -Online
```

### Q: 重新安装 / 升级依赖？

```batch
deploy.bat -Clean
```
此命令会先清理已安装的 PIL、PySide6、shiboken6、psd_tools、numpy 等目录，再重新安装。

### Q: UE 编辑器中看不到 AssetCustoms 菜单？

1. 确认 `AssetCustoms.uplugin` 所在目录位于项目 `Plugins/` 下
2. 确认 `deploy.bat` 已成功运行（窗口显示 "Installation complete!"）
3. 检查 UE Output Log 中 `LogPython` 的错误信息
4. 编辑器 → Edit → Plugins → 搜索 "AssetCustoms" 确认已启用

### Q: 如何使用 Send to Photoshop？

1. 在 Content Browser 中选中一个或多个 Texture2D 资产
2. 右键 → **Send** → **Send to Photoshop**
3. 插件会自动导出贴图为 PSD，启动 Photoshop 打开
4. 在 Photoshop 中编辑并保存后，贴图会自动重新导入到 UE（保留压缩、sRGB、LOD 设置）
5. 关闭 Photoshop 后临时文件自动清理

> 需要系统已安装 Adobe Photoshop（自动搜索 `C:\Program Files\Adobe\` 路径）。

### Q: 如何使用 Send to Substance Painter？

1. 在 Content Browser 中选中一个 **StaticMesh** 资产
2. 右键 → **Send** → **Send to Substance Painter**
3. 插件自动收集材质信息、导出 FBX 和贴图，发送到 SP 创建项目
4. SP 中自动创建 Fill Layer 并按 Config Profile 的 `parameter_bindings` 映射通道
5. 在 SP 中编辑贴图后点击 **SYNC**，自动按 UE 原始格式回传刷新

> **前置条件**：SP 以 `--enable-remote-scripting` 启动，SPsync 插件已安装。
> **Config Profile**：导入时自动打标签到 SM/MI 元数据，Send to SP 时读取并驱动映射。支持 Content Browser 右键 View/Set/Clear Profile。

### Q: max_resolution 如何控制贴图尺寸？

`max_resolution` 是一个 **整数**（POT 值，如 512、1024、2048、4096），定义在 `processing.texture_definitions[].max_resolution` 和 `output.texture_import_defaults.max_resolution` 中。全管线统一生效：
- **UE 导入**：设置 `max_texture_size` 属性限制运行时分辨率
- **SP 项目创建**：作为 `default_texture_resolution` 初始化 TextureSet 分辨率
- **SP 导出**：转换为 `sizeLog2` 控制导出尺寸

---

如需贡献或提问，请先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
