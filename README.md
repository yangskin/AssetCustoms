# AssetCustoms — UE5 资产自动化插件

> 版本: V1.5（Widget Send to Photoshop）
> 引擎: Unreal Engine 5.7
> 语言: Python（UE Editor Python）+ C++（Editor Module）

AssetCustoms 是一个给 Unreal Engine 项目用的资产自动化插件。

说人话，它做的事很简单：把外部素材导进 UE 这件事，从“每次靠人手动收拾”变成“按项目规则自动整理好”。

它不只是导入工具，还负责把资产处理成团队能直接用的状态，比如命名统一、贴图通道整理、材质实例创建、导入参数设置，以及和 Photoshop、Substance Painter 的往返修改。

> 注意：AssetCustoms 是 UE 侧插件；SPsync 是 Substance Painter 侧插件。两者配合使用，但分别安装、分别发布。

---

## 目录

- [功能定位](#功能定位)
- [主要功能](#主要功能)
- [如何部署](#如何部署)
- [细节说明](#细节说明)
- [常见问题](#常见问题)

---

## 功能定位

### 它是干什么的？

AssetCustoms 的定位可以概括成一句话：

**它是项目资产管线里的“标准化守门员”。**

外部资产进项目以后，最麻烦的通常不是“导进来”，而是后面那一串重复劳动：

- 命名要不要改
- 贴图怎么识别
- 哪张图进哪个材质参数
- 导入设置怎么统一
- 贴图尺寸怎么限制
- 做完以后怎么回到 Photoshop 或 Substance Painter 继续改

AssetCustoms 就是把这些重复操作收进一套配置驱动的流程里。

### 它解决什么问题？

如果团队里遇到下面这些情况，这个插件就有价值：

- 同一种资产，不同人导入出来的结果不一样
- 贴图命名和通道经常出错，TA 总要返工
- 材质实例创建、参数绑定、导入设置全靠手工点
- UE 和 Photoshop / Substance Painter 来回改图太慢
- 项目想把资产规范固化下来，但总是落不到工具层

### 一句话介绍版本

如果你要在汇报、立项或者 README 首屏里快速介绍它，可以直接用这句：

> AssetCustoms 是一个面向 UE5 项目的资产自动化插件，用配置驱动方式把外部素材整理成符合项目规范的可用资产，并打通 UE 与 Photoshop、Substance Painter 的往返编辑流程。

---

## 主要功能

下面按使用者最关心的角度来讲，不按开发代号来堆功能名。

### 1. 资产导入后自动标准化

这是插件最核心的能力。

导入 FBX、贴图和相关资源后，插件可以按配置自动完成下面这些事：

- 扫描并加载 Profile 配置
- 识别贴图类型和用途
- 处理 FBX 内嵌贴图
- 检查资产数量、材质、贴图映射是否完整
- 发现问题时弹出分诊界面，而不是静默失败
- 自动重命名资产
- 自动创建材质实例
- 自动把贴图绑定到正确的材质参数
- 自动应用统一的导入设置
- 自动做清理和收尾

简单说，就是把“导入后整理资产”这件事批量自动化了。

### 2. 配置驱动，而不是写死规则

AssetCustoms 不是把规则写死在代码里，而是把流程拆成了三段：

- `input`：识别进来的是什么
- `processing`：决定怎么处理
- `output`：决定最终怎么落到项目里

这意味着它适合项目长期使用。规则变了，多数情况下改配置就行，不用每次改代码。

同时还提供了 Config Editor，可以直接在图形界面里编辑配置，而不是全靠手改 JSONC。

### 3. 支持批量处理

如果一次要导很多资产，插件支持多 FBX 批处理和分诊排队，不需要一个个手动处理。

这个能力对外包交付、资产集中入库、阶段性合并内容时很有用。

### 4. Photoshop 往返编辑

插件支持从 UE 里直接把贴图送到 Photoshop，改完保存后自动回写。

目前支持两类场景：

- Content Browser 里选中 Texture2D，右键发送到 Photoshop
- Widget Blueprint 编辑器里选中 Image 控件，把它绑定的贴图直接发到 Photoshop

这套流程的价值不在“能打开 PS”，而在于：

- 自动导出
- 自动监控文件变化
- 自动重新导入 UE
- 尽量保留原来的压缩、sRGB、LOD 等设置
- 避免编辑器被强行抢焦点

### 5. Substance Painter 往返同步

AssetCustoms 可以把 Static Mesh 从 UE 发送到 Substance Painter，并通过 SPsync 完成双向协作。

支持的入口包括：

- Content Browser 右键发送 StaticMesh
- Level Editor 里选中 Actor 后右键发送

发送后，工具会自动做这些事：

- 收集材质信息
- 导出 FBX 和贴图
- 把数据包发送到 SP
- 按 Config Profile 建立通道映射
- 编辑完成后从 SP 回传到 UE

如果团队日常在 UE 和 SP 之间反复来回，这个能力能省掉大量重复动作。

### 6. 贴图尺寸统一控制

`max_resolution` 会贯穿整条流程：

- UE 导入时限制最大贴图尺寸
- SP 创建项目时设定 TextureSet 分辨率
- SP 导出时控制最终输出尺寸

这对控制项目贴图规格特别重要，能避免“有人导 4K，有人导 1K”的混乱情况。

### 7. Widget 编辑器增强

除了资产导入管线，插件还补了一些非常实用的 UI 编辑能力。

#### 粘贴图片到 Widget

在 Widget 编辑器里，可以直接把系统剪贴板里的截图或 PNG 粘贴成 Image 控件。

特点：

- 支持快捷键 `Ctrl+Shift+V`
- 自动创建 Texture 资产
- 自动保存到 Widget 同目录
- 支持去重，重复图片不会反复生成新资产
- 失败时有明确提示，不会闷声出错

#### Widget 贴图直接送 Photoshop

在 Designer 视图里右键选中的 Image 控件，可以把它绑定的贴图直接发去 Photoshop，改完再自动回到 UE。

这对 UI 迭代很顺手，尤其是需要频繁修图标、面板、按钮贴图的场景。

### 8. 当前已覆盖的能力清单

如果你想快速看功能范围，可以看这张表：

| 模块 | 说明 | 状态 |
|------|------|------|
| 配置系统 | JSONC Profile 扫描、加载、校验 | ✅ |
| 智能导入 | Content Browser 下拉、文件对话框、隔离区导入 | ✅ |
| 嵌入贴图处理 | FBX 内嵌贴图识别与处理 | ✅ |
| 检查链 + 分诊 UI | 自动检查并弹出修正界面 | ✅ |
| 标准化引擎 | 重命名、贴图处理、MIC 创建、材质绑定、清理 | ✅ |
| 批处理 | 多 FBX 批量导入、分诊排队 | ✅ |
| Config Editor | Input / Processing / Output 图形化编辑 | ✅ |
| Photoshop 联动 | 贴图发送到 PS 并自动回写 | ✅ |
| Substance Painter 联动 | 发送 SM 到 SP，按配置映射并回传 | ✅ |
| 贴图尺寸控制 | `max_resolution` 全流程统一 | ✅ |
| Widget 粘贴图片 | 剪贴板图片一键变成 Image 控件 | ✅ |
| Widget 发送到 Photoshop | Widget 中的 Image 贴图直接送 PS | ✅ |

详细里程碑可参考 [docs/roadmap.md](docs/roadmap.md)。

---

## 如何部署

### 前置条件

| 项目 | 要求 |
|------|------|
| 引擎 | Unreal Engine 5.5+（当前开发基于 5.7） |
| 系统 | Windows 10/11 64-bit |
| 插件位置 | 项目 `Plugins/AssetCustoms/` 目录 |

### 最快部署方式

如果你只想先跑起来，按这 3 步做就行：

```text
1. 把 AssetCustoms 文件夹放到项目的 Plugins/ 目录下
2. 双击 deploy.bat 安装依赖
3. 启动 UE 编辑器，看到工具栏里的 AssetCustoms 菜单
```

### 方式一：双击 deploy.bat（推荐）

这是最适合普通用户的方式。

双击 `deploy.bat` 后，脚本会自动完成这些动作：

1. 查找系统里的 PowerShell（`powershell` 或 `pwsh`）
2. 用 `-ExecutionPolicy Bypass` 调用 `deploy.ps1`
3. 自动查找 UE 自带的 Python 解释器
4. 优先从 `vendor/` 安装离线 wheel 包
5. 如果离线包不可用，再回退到 PyPI 在线安装
6. 自动验证 Pillow 和 PySide6 是否可用

目录结构大概是这样：

```text
Plugins/AssetCustoms/
  deploy.bat
  deploy.ps1
  vendor/
    pillow-12.1.1-cp311-cp311-win_amd64.whl
    pyside6_essentials-6.10.2-cp39-abi3-win_amd64.whl
    shiboken6-6.10.2-cp39-abi3-win_amd64.whl
```

#### 常用参数

```batch
:: 默认安装（离线优先）
deploy.bat

:: 强制在线安装
deploy.bat -Online

:: 清理后重新安装
deploy.bat -Clean

:: 手动指定 Python 解释器
deploy.bat -PythonExe "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
```

### 方式二：直接运行 deploy.ps1

适合已经习惯用 PowerShell 的开发者。

```powershell
# 在 AssetCustoms 目录下执行
.\deploy.ps1

# 或显式使用 bypass
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

### 方式三：手动 pip 安装

如果自动脚本失败，可以手动装。

```powershell
# UE 自带 Python 路径示例
$py = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"

# 从 vendor 离线安装
& $py -m pip install vendor\pillow-12.1.1-cp311-cp311-win_amd64.whl vendor\pyside6_essentials-6.10.2-cp39-abi3-win_amd64.whl vendor\shiboken6-6.10.2-cp39-abi3-win_amd64.whl --target Content\Python --upgrade --no-deps

# 或从 PyPI 在线安装
& $py -m pip install -r requirements.txt --target Content\Python --upgrade
```

### 安装完成后怎么验证？

可以用两种方式检查：

#### 方式一：看编辑器界面

1. 启动 UE 编辑器并打开项目
2. 打开 Content Browser
3. 看工具栏里是否出现 `AssetCustoms` 下拉菜单

#### 方式二：看 Python 是否可用

在 UE Editor 的 Python 控制台里执行：

```python
from PIL import Image
print(Image.__version__)

from PySide6 import QtCore, QtWidgets
print(QtCore.qVersion())
```

如果都能正常输出版本号，说明依赖基本没问题。

### 依赖会装到哪里？

所有依赖都会安装到插件自己的 `Content/Python/` 目录。

这样做的好处是：

- 不污染系统 Python
- 不改 UE 引擎目录
- 每个项目的依赖可以独立管理

### 运行时依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| Pillow | ≥ 10.0.0 | 贴图通道编排、格式转换 |
| PySide6-Essentials | ≥ 6.5.0 | 分诊 UI、Config Editor 等 Qt 界面 |
| shiboken6 | ≥ 6.5.0 | PySide6 运行时依赖 |
| psd-tools | ≥ 1.9.0 | PSD 文件读写（Send to Photoshop） |

---

## 细节说明

### 1. 它是怎么工作的？

可以把 AssetCustoms 理解成一条自动化管线：

```text
外部资产 -> 识别类型 -> 检查问题 -> 按规则处理 -> 生成规范资产 -> 需要时送去 PS / SP -> 修改后回传 UE
```

也就是说，它不是只负责“导入那一下”，而是尽量覆盖资产从进项目到可继续迭代的整个过程。

### 2. 配置架构：Input -> Processing -> Output

V2.0 之后，配置被拆成了三段，目的就是让职责更清楚。

#### Input

负责回答一个问题：**进来的东西是什么？**

典型内容包括：

- 贴图匹配规则
- 文件名识别方式
- glob / regex 匹配
- 优先级

#### Processing

负责回答：**识别出来以后怎么处理？**

典型内容包括：

- 冲突策略
- Mesh 导入设置
- 贴图通道编排
- 输出格式
- 位深
- sRGB / mips 等处理规则

#### Output

负责回答：**最后要生成成什么样？**

典型内容包括：

- 目标路径和子目录
- 命名模板
- 母材质与参数绑定
- 导入默认值
- 针对不同贴图的 override 规则

这套设计的好处是，规则更容易维护，也更适合长期项目演进。

### 3. 与 SPsync 的关系

AssetCustoms 负责 UE 侧，SPsync 负责 Substance Painter 侧。

两者配合关系如下：

| 插件 | 安装位置 | 职责 |
|------|----------|------|
| AssetCustoms | UE 项目 `Plugins/AssetCustoms/` | 收集 UE 资产、导出、发送、回传刷新 |
| SPsync | Substance Painter 插件目录 | 建项目、做通道映射、导出、同步回 UE |

通信方式：

- UE -> SP：HTTP POST 到 SP Remote Scripting API（默认 `localhost:60041`）
- SP -> UE：Remote Execution TCP 协议（默认 `localhost:6776`）

使用前请确认：

- Substance Painter 以 `--enable-remote-scripting` 启动
- SPsync 已正确安装并启用
- AssetCustoms 依赖已部署完成

### 4. Widget 相关功能的实现思路

这部分不是给普通使用者看的，是给维护者快速建立概念的。

#### 粘贴图片到 Widget

流程如下：

```text
剪贴板图片 -> 读取像素 -> 计算 MD5 去重 -> 创建 Texture2D -> 保存到 Widget 同目录 -> 创建 UImage -> 刷新 Designer
```

关键点：

- 支持 `CF_DIB` / `CF_DIBV5`
- 支持 Alpha
- 重复图片复用已有 Texture
- 失败时给出明确提示

#### Widget 发图到 Photoshop

流程如下：

```text
选中 UImage -> 取出 Brush 里的 Texture2D -> C++ 调 Python -> 导出 PNG -> 启动 Photoshop -> 监控文件变化 -> 自动重导入
```

关键点：

- 只在选中有效 Image 控件时显示菜单
- 通过 `IPythonScriptPlugin::ExecPythonCommand()` 做桥接
- 自动回写时尽量不打断编辑器工作流

### 5. 目录结构

```text
AssetCustoms/
├── AssetCustoms.uplugin
├── deploy.bat
├── deploy.ps1
├── requirements.txt
├── requirements-dev.txt
├── run_tests.py
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── Content/
│   ├── Config/AssetCustoms/
│   └── Python/
│       ├── init_unreal.py
│       ├── core/
│       ├── unreal_integration/
│       └── unreal_qt/
├── vendor/
├── docs/
├── standards/
└── Tests/
```

### 6. 开发与测试

#### 纯 Python 测试

核心逻辑可以不启动 UE，直接在普通 Python 环境下测试：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python run_tests.py

# 或者
pytest Content/Python/core/tests/ -v --tb=short
```

#### UE 编辑器内验证

1. 启动 UE 编辑器
2. 打开项目
3. 打开 Output Log
4. 搜索 `LogPython`
5. 检查工具栏和右键菜单是否正常出现

#### 开发提示

- UE 会缓存已导入的 Python 模块，改完 `.py` 后通常需要 `importlib.reload()` 或重启编辑器
- 变更公共行为时，建议同步更新文档
- 尽量避免在主线程里做长时间阻塞操作

### 7. 文档导航

| 文档 | 说明 |
|------|------|
| [docs/roadmap.md](docs/roadmap.md) | 路线图、里程碑与进度 |
| [docs/architecture.md](docs/architecture.md) | 系统架构、模块边界、数据流 |
| [docs/requirements_v1.1.md](docs/requirements_v1.1.md) | V1.1 需求规格 |
| [docs/testing.md](docs/testing.md) | 测试说明与环境配置 |
| [docs/decisions/](docs/decisions/) | 架构决策记录 |
| [standards/coding-style.md](standards/coding-style.md) | 编码规范 |
| [standards/review-checklist.md](standards/review-checklist.md) | Code Review 检查单 |
| [standards/commit-convention.md](standards/commit-convention.md) | 提交规范 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [SECURITY.md](SECURITY.md) | 安全策略 |

---

## 常见问题

### 双击 deploy.bat 没反应怎么办？

先确认 PowerShell 是否可用。Windows 终端里执行：

```powershell
powershell --version
```

Windows 10/11 一般都自带 PowerShell 5.1。

### 提示找不到 pip 怎么办？

UE 自带 Python 默认包含 pip。你可以手动指定解释器：

```batch
deploy.bat -PythonExe "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
```

### vendor 里的 wheel 和当前 Python 不匹配怎么办？

当前内置 wheel 主要面向 UE 5.7 的 Python 3.11。版本不匹配时，直接走在线安装：

```batch
deploy.bat -Online
```

### 想重新安装依赖怎么办？

```batch
deploy.bat -Clean
```

它会先清理旧依赖，再重新安装。

### 编辑器里看不到 AssetCustoms 菜单怎么办？

按这个顺序排查：

1. 确认插件目录在项目的 `Plugins/` 下
2. 确认 `deploy.bat` 已成功执行
3. 看 UE Output Log 里的 `LogPython` 报错
4. 在 Edit -> Plugins 里确认 AssetCustoms 已启用

### 怎么用 Send to Photoshop？

#### Content Browser 里使用

1. 选中一个或多个 Texture2D
2. 右键 `Send -> Send to Photoshop` 或 `Send to Photoshop as PNG`
3. Photoshop 打开后直接修改并保存
4. UE 会自动重新导入

#### Widget 编辑器里使用

1. 打开 Widget Blueprint
2. 在 Designer 里选中一个 Image 控件
3. 右键 `Send to Photoshop (PNG)`
4. 修改保存后会自动回写到 UE

### 怎么用 Send to Substance Painter？

#### Content Browser 里使用

1. 选中一个 StaticMesh
2. 右键 `Send -> Send to Substance Painter`

#### Level Editor 里使用

1. 在视口里选中带 StaticMeshComponent 的 Actor
2. 右键 `Send -> Send to Substance Painter`
3. 插件会自动提取对应 StaticMesh，并沿用同一套流程

通用流程是：

1. UE 收集材质和贴图信息
2. 导出 FBX 与贴图
3. 发送到 SP 建项目
4. SP 里编辑完成后通过 SYNC 回传

### `max_resolution` 是做什么的？

它是整条管线里的统一贴图尺寸控制项。

例如设成 `1024`，它会同时影响：

- UE 导入时的最大贴图尺寸
- SP 项目创建时的默认分辨率
- SP 导出时的输出尺寸

如果你想控制项目贴图规格，这个参数很关键。

---

如需贡献或提问，请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。