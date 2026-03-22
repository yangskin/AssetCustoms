# 系统架构 / 模块边界 / 数据流（V1.1）

本项目位于 Unreal Engine 插件的 Python 侧，主要用于资源处理与工具自动化，围绕“静默成功，响亮失败”的 UX 模型构建。

> 实现状态（2026-03-22）
> - 已完成：FR1 配置系统 ✅；FR2 智能导入核心流程 ✅；FR2.5 原生嵌入贴图管线 ✅（含内部贴图优先、自动材质绑定读取）；FR3 检查链 ✅；FR5 标准化引擎 ✅（含 SM→MI 绑定修复、MM_Prop_PBR 母材质创建）。
> - 进行中：FR4 分诊 UI（PySide6 + unreal_qt 基础设施已就绪，待实现业务窗口）；Config Schema v1.1 剩余字段；M3 质量与体验。
> - 基础设施：PySide6-Essentials 6.10.2 + shiboken6 6.10.2 已集成（离线 wheel + deploy.ps1）；`unreal_qt` 模块提供 Qt/UE 非阻塞共存。

## 作用域与边界
- 边界：仅覆盖 UE Python 脚本与其交互的最小外部接口（Editor、AssetTools、EUL、材质系统、文件对话框）。
- 非目标：不直接修改 UE C++ 核心；不引入重量级依赖（Pillow、json5、PySide6-Essentials 属于轻依赖并随插件内置）。

## 顶层视图（模块概览）
- 入口：`init_unreal.py`
  - 初始化日志与异常捕获；注册“内容浏览器工具栏下拉按钮”。
  - 扫描配置目录，加载 Profile（JSON/JSONC）。
- 模块 A：Profile/配置管理（FR1）
  - 扫描目录、解析 JSONC、校验 config_version 与 Schema v1.1。
  - 暴露 Profile 列表供 UI 填充；提供占位符替换工具（{Name}/{Category}/{DropDir} 等）。
- 模块 B：“智能导入”入口（FR2）
  - 内容浏览器工具栏下拉按钮，动态填充 Profile。
  - 在选择 Profile 后带上下文文件选择（.fbx），计算“隔离区”路径并导入 FBX+纹理。
- 模块 C：自动化检查链（FR3）
  - 检查模型数量（仅 1 个 StaticMesh）。
  - 主材质可用性检查（允许空路径跳过 MIC）。
  - 贴图映射：优先从 FBX 材质节点“智能预填充”，其次应用规则匹配（glob/regex+priority）。
- 模块 D：分诊 UI（FR4）
  - 仅在检查失败时弹出；展示失败原因、已识别结果；对未映射槽提供下拉选择；支持 Base_Name 确认；触发执行。
- 模块 E：标准化执行引擎（FR5）
  - 贴图处理（Pillow）：通道编排、常量/反相/remap、normal G 反转、可选缩放、格式/位深保存。
  - 资产重命名与移动：根据 target_path_template、asset_naming_template、conflict_policy 实施。
  - 材质实例创建与链接：父材质=default_master_material_path，参数按定义自动绑定。
  - 资产链接与清理：SM 绑定 MI；清理隔离区；应用导入设置（压缩、LOD 组、sRGB、VT 等）。

## 数据流（时序）
1) UE 加载插件 -> `init_unreal.py` 注册 UI 与加载 Profile 列表。
2) 用户选择“AssetCustoms: 智能导入 ▼”中的某 Profile -> 打开 .fbx 文件对话框。
3) 计算隔离区路径，导入 FBX 与纹理（按 search_roots）。
4) 检测贴图来源：
   - 路径 A（外部贴图）：磁盘上有匹配的贴图文件 → 触发检查链（FR3）→ 标准化引擎（FR5）。
   - 路径 B（嵌入贴图）：磁盘无贴图但 UE 隔离区有 Texture2D → 原生嵌入管线（FR2.5）。
5) 路径 A 分支：
   - 成功：进入标准化引擎（Pillow 贴图处理、重命名/移动、MIC 创建/链接、导入设置、清理）-> 通知成功。
   - 失败：保留隔离区并弹出分诊 UI -> 用户补全 -> 再次执行标准化引擎。
6) 路径 B 分支（FR2.5）：
   - 删除自动创建的材质 → 三层策略匹配贴图到逻辑位 → 重命名贴图 → 移动 SM → 创建 MI → 链接 → 清理。
   - 跳过 Pillow 通道编排，保留 UE 原生贴图质量。
   - **内部贴图优先**：Phase 3.5 无条件以自动材质绑定（`texture_parameter_values`）覆盖外部匹配结果。
   - **自动材质绑定读取**：`read_material_texture_bindings()` 从 FBX 自动创建的 MIC 读取精准贴图→逻辑槽映射；`FBX_PARAM_TO_SLOT` 将 DiffuseColorMap 等 FBX 参数名转为 BaseColor 等逻辑槽。

## SM→MI 绑定与母材质（2026-03-22）
- **SM→MI 绑定方式**：`mesh.set_material(slot, mi)`（UE 原生 API）。
  - ⚠ `set_editor_property("static_materials", ...)` 对 `FStaticMaterial`（值类型）写回无效，不可使用。
- **MM_Prop_PBR 母材质** (`/Game/MyProject/Materials/Masters/MM_Prop_PBR`)：
  - 4 个 TextureSampleParameter2D：
    - `BaseColor_Texture` (SamplerType=Color) → BaseColor 输出
    - `Normal_Texture` (SamplerType=Normal) → Normal 输出
    - `Packed_Texture` (SamplerType=LinearColor) → Metallic(R) / Roughness(G) / AO(B)
    - `Height_Texture` (SamplerType=LinearColor) → 预留
  - MI 创建时自动以此为 Parent，贴图参数按 `_texture_slot_to_mi_param` 映射绑定。

## 目录结构（当前）
```
AssetCustoms/                      # 插件根目录（当前仓库根）
  ├─ AssetCustoms.uplugin          # Unreal 插件描述文件
  ├─ Content/
  │   └─ Python/
  │       ├─ init_unreal.py        # UE Python 入口脚本
  │       ├─ core/                 # 纯 Python 核心（无 Unreal 依赖）
  │       ├─ unreal_integration/   # Unreal API 桥接层
  │       └─ unreal_qt/            # PySide6 Qt 集成层（详见下方）
  │           ├─ __init__.py       # QApplication 管理 / tick 挂载 / widget 生命周期
  │           └─ dark_bar.py       # 无边框暗色标题栏（DarkBar / FramelessWindow）
  ├─ vendor/                       # 离线 wheel 包（不提交安装产物，仅 .whl）
  │   ├─ pillow-*.whl
  │   ├─ pyside6_essentials-*.whl
  │   └─ shiboken6-*.whl
  ├─ deploy.ps1                    # 依赖安装脚本（离线优先 → PyPI 回退）
  ├─ requirements.txt              # 运行时依赖声明
  ├─ docs/                         # 项目文档
  │   ├─ architecture.md
  │   ├─ requirements_v1.1.md
  │   ├─ roadmap.md
  │   └─ decisions/
  │       └─ ADR-0001.md
  ├─ standards/                    # 规范与指南
  │   ├─ coding-style.md
  │   ├─ review-checklist.md
  │   └─ commit-convention.md
  ├─ Tests/                        # 测试脚本
  │   └─ test_qt_messagebox.py     # PySide6 集成验证
  ├─ README.md                     # 文档索引与导航（根级）
  ├─ CONTRIBUTING.md               # 贡献指南（根级）
  └─ SECURITY.md                   # 安全策略（根级）
```

## 模块契约（摘要）
- 配置管理（FR1）
  - 输入：配置目录路径；JSON/JSONC 文件。
  - 输出：Profile 列表与解析后的配置对象；Schema 校验结果。
  - 错误：无配置或解析失败 -> 在 UI 禁用入口并提示（NFR4）。
- 智能导入（FR2）
  - 输入：Profile 选择、当前内容浏览器路径、FBX 文件路径。
  - 输出：隔离区内的导入资产（SM、Textures、FBX 材质）。
  - 错误：Current_Path 非法 -> 使用 default_fallback_import_path。
- 检查链（FR3）
  - 输入：隔离区资产、Selected_Profile。
  - 输出：映射结果（逻辑槽 -> 源贴图）。
  - 错误：数量不符/主材质缺失/映射不完整或歧义 -> 分诊 UI。
- 分诊 UI（FR4）
  - 输入：失败原因与部分映射；孤儿贴图列表。
  - 输出：用户补全后的映射与 Base_Name 确认。
- 标准化引擎（FR5）
  - 输入：映射、Selected_Profile、Base_Name、隔离区路径。
  - 输出：最终路径中的标准化资产（SM/Textures/MIC）；导入设置已应用。
  - 错误：任何步骤失败 -> 停止、记录日志、保留隔离区（NFR3）。

## 性能与扩展
- 性能预算：典型资产从导入到清理 ≤ 5s（NFR1）。
- I/O 最小化：尽量内存中合成贴图，批量保存；避免不必要的磁盘往返。
- 可扩展性：Profile Schema 向后兼容；规则扩展不破坏现有配置。

## PySide6 / unreal_qt 集成（2026-03-22）

### 概述

为 FR4 分诊 UI 及后续自定义编辑器窗口需求，集成 PySide6 作为 Qt 前端层。通过 `unreal_qt` 模块实现 Qt 事件循环与 UE Editor 主循环的非阻塞共存。

### 依赖与安装

| 包名 | 版本 | 用途 | wheel 文件 |
|------|------|------|------------|
| PySide6-Essentials | ≥ 6.5.0 (当前 6.10.2) | QtCore / QtGui / QtWidgets 等核心模块 | `vendor/pyside6_essentials-*.whl` |
| shiboken6 | ≥ 6.5.0 (当前 6.10.2) | PySide6 的 C++ 绑定运行时 | `vendor/shiboken6-*.whl` |

- **不安装 PySide6-Addons**（~165 MB，含 Qt3D/QtCharts 等，当前无需）。
- 安装方式：`deploy.ps1` 离线优先（从 `vendor/` 安装 `.whl`），回退 PyPI 在线安装。
- 安装目标：`Content/Python/`（UE 自动加入 `sys.path`）。

### unreal_qt 模块架构

```
unreal_qt/
├── __init__.py     # QApplication 初始化 + tick 挂载 + widget 管理
└── dark_bar.py     # 自定义无边框窗口 + Unreal 风格暗色标题栏
```

#### `__init__.py` — 核心机制

| 函数/类 | 职责 |
|---------|------|
| `setup()` | 创建/复用 `QApplication` 实例，设置 HighDPI 策略 |
| `widget_manager` | 持有 widget 引用防止 GC，管理生命周期 |
| `wrap(widget)` | 将 widget 加入 `widget_manager` |
| `parent_orphan_widgets()` | 查找未挂载的顶层 Qt 窗口，通过 `unreal.parent_external_window_to_slate()` 挂载到 UE 主窗口 |
| `tick(delta)` | 注册到 `unreal.register_slate_post_tick_callback`，每 0.3s 检查并挂载孤儿窗口 |

**关键设计**：Qt 不运行独立事件循环（不调用 `app.exec()`），而是依赖 UE 的 Slate tick 回调驱动 Qt 事件处理，避免阻塞编辑器。

#### `dark_bar.py` — UI 组件

| 类 | 职责 |
|----|------|
| `DarkBar` | 自定义暗色标题栏（最小化/最大化/关闭按钮），支持拖拽移动 |
| `DarkBarUnreal` | 继承 `DarkBar`，使用 UE 引擎 Slate SVG 图标替换文字按钮 |
| `FramelessWindow` | 无边框窗口容器，内含 `DarkBar` + `content_layout` |
| `FramelessWindowUnreal` | 使用 `DarkBarUnreal` 的 UE 风格无边框窗口 |
| `wrap_widget_unreal()` | 辅助函数：将任意 QWidget 包装为 `FramelessWindowUnreal` |

### PySide6 在 UE 中的注意事项

| 事项 | 说明 |
|------|------|
| **模块缓存** | UE 缓存已导入的 Python 模块，修改 `.py` 后需 `importlib.reload()` 或重启 Editor |
| **QWidget.close** | 是方法（slot），不是信号，不可 `.connect()` |
| **HighDPI** | PySide6 默认启用 HighDPI，已移除的 `AA_EnableHighDpiScaling` / `AA_UseHighDpiPixmaps` 不可使用 |
| **import unreal** | 远程执行脚本中需显式 `import unreal`，不会自动注入 |
| **unreal_stylesheet** | 当前未安装，已从 `__init__.py` 移除引用；如需暗色样式可后续集成 |

### 创建 UI 的快速模板

```python
import unreal
import unreal_qt
from PySide6 import QtWidgets

unreal_qt.setup()

# 方式 1：简单对话框
msg = QtWidgets.QMessageBox()
msg.setWindowTitle("标题")
msg.setText("内容")
msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
msg.show()
unreal_qt.wrap(msg)

# 方式 2：自定义窗口（Unreal 风格无边框）
from unreal_qt.dark_bar import FramelessWindowUnreal

window = FramelessWindowUnreal(title="My Tool")
label = QtWidgets.QLabel("Hello from PySide6!")
window.setCentralWidget(label)
window.resize(400, 300)
window.show()
unreal_qt.wrap(window)
```

### 验证状态
- ✅ `deploy.ps1` 离线安装通过（Pillow 12.1.1 + PySide6 6.10.2）
- ✅ `Tests/test_qt_messagebox.py` 在 UE Editor 中成功弹出 QMessageBox

## 参考
- 路线图：[docs/roadmap.md](./roadmap.md)
- 需求规格（V1.1）：[./requirements_v1.1.md](./requirements_v1.1.md)
- 编码规范（Google Python）：[../standards/coding-style.md](../standards/coding-style.md)

## 模块拆分与边界（v1.1）

为提升可测试性与可复用性，代码分为两层：

- 核心模块（pure Python）：`Content/Python/core`
  - 无 Unreal 依赖，可在本地/CI 独立运行与测试。
  - 领域能力：贴图图层合并（`core/textures/layer_merge.py`）、配置解析（`core/config/{schema,loader}.py`）。

- Unreal 适配层：`Content/Python/unreal_integration`
  - 负责桥接 Unreal API，将 Texture/设置转为核心模块可消费的数据结构。
  - 不包含业务算法，仅做 IO/类型适配与落地（像素读取/写回、项目设置读取等）。

依赖方向：`unreal_integration -> core`，禁止反向依赖。

集成方式：`init_unreal.py` 仅注册 UI/入口，并按需导出 `BlendMode`、`merge_textures_in_unreal`、`load_project_config` 等常用 API。

### 近期实现要点（同步）
- 文件对话框：当前使用 tkinter 的 `filedialog.askopenfilenames` 作为统一方案，仅选择 .fbx（开发期更轻量，跨平台）；不再依赖 `EditorDialog`/`DesktopPlatform` 回退。
- 配置：实现轻量 JSONC 解析器（优先 `json5`，否则剥离注释+尾逗号），并提供 `load_config()` 将 `.jsonc/.json` 解析为 `PluginConfig` 数据类。
- 默认配置：新增 `Content/Config/AssetCustoms/Prop.jsonc`，可作为 Profile 被扫描。

（更多测试与运行信息见：[docs/testing.md](./testing.md)）

## UI 变更记录（2025-11-05）

- 工具栏入口：由“单一按钮（Import FBX…）”调整为“下拉菜单（AssetCustoms ▼）”。
- 菜单项来源：自动扫描 `Content/Config/AssetCustoms/*.jsonc`，每个配置文件对应一个菜单项；点击后执行 FBX 选择流程并记录所选预设。
- 扩展方式：新增配置只需在上述目录放入 `*.jsonc` 文件，无需改动代码；热重载时菜单会自动替换。

### 导入上下文构建（2025-11-05）

- 新增 `unreal_integration.import_context.ImportContext` 数据类：
  - `fbx_path: str`、`content_path: str`（Content Browser 当前路径）、`profile: PluginConfig`、`profile_path: str`。
- 新增 `build_import_context(fbx_path, profile_path)`：
  - 使用 `core.config.loader.load_config()` 解析 `.jsonc/.json` 预设；
  - 采样当前 Content Browser 路径（失败回退 `/Game`）。
- UI 回调 `on_pick_fbx_with_preset` 已接入该函数，构建完成后在日志中输出摘要；后续 FR2/FR3 将以此作为统一入口继续执行导入与检查链。
