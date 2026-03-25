# 系统架构 / 模块边界 / 数据流（V1.1）

本项目位于 Unreal Engine 插件的 Python 侧，主要用于资源处理与工具自动化，围绕“静默成功，响亮失败”的 UX 模型构建。

> 实现状态（2026-03-25）
> - 已完成：FR1 配置系统 ✅；FR2 智能导入核心流程 ✅；FR2.5 原生嵌入贴图管线 ✅（含内部贴图优先、自动材质绑定读取）；FR3 检查链 ✅；FR4 分诊 UI ✅（PySide6 TriageWindow + TriageDecision + 8 项单测 + 视觉验证）；FR5 标准化引擎 ✅（含 SM→MI 绑定修复、MM_Prop_PBR 母材质创建）。
> - 已完成：M3 质量与体验 ✅（NFR1 性能预算 + NFR3 健壮性 + NFR4 无配置 UI 禁用）；M4 批处理 ✅；Config Editor GUI（Round 1-5，含多语言支持）。
> - 已完成：M6 Send to Photoshop ✅（Content Browser 右键 → Send → Send to Photoshop，PSD 导出/监控/自动回写）。
> - 已完成：M7 Send to Substance Painter ✅（Content Browser 右键 → Send → Send to Substance Painter，含 Config Profile Tag / 多 TextureSet / Grayscale Filter / Round-Trip Sync，SPsync 185 tests passed）。
> - 健壮性审计（2026-03-23）：修复 7 项问题（tick 定时器、内存泄漏、静默异常、输入校验等），详见「健壮性与稳定性审计」章节。
> - 基础设施：PySide6-Essentials 6.10.2 + shiboken6 6.10.2 + psd-tools 1.14.2 已集成（离线 wheel + deploy.ps1）；`unreal_qt` 模块提供 Qt/UE 非阻塞共存。

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
  - 资产重命名与移动：根据 target_path_template、asset_naming_template、conflict_policy 实施；按 asset_subdirectories 将 SM/MI/贴图分别放入对应子目录。
  - 材质实例创建与链接：父材质=default_master_material_path，参数按定义自动绑定。
  - 资产链接与清理：SM 绑定 MI；清理隔离区；应用导入设置（压缩、LOD 组、sRGB、VT 等）。

## 模块 F：外部编辑器桥接（Send to Photoshop）
- `unreal_integration/photoshop_bridge.py`：PhotoshopBridge + TextureMonitor + TickTimer
- 功能：Content Browser 右键 → Send → Send to Photoshop
- 流程：导出 Texture2D → TGA → PSD（psd-tools）→ 启动 Photoshop → TextureMonitor 轮询文件变化 → 自动重新导入 → PS 关闭后清理临时文件
- 依赖：Pillow（TGA→Image 转换）、psd-tools（PSD 格式读写）
- 注册：`ui.py._register_asset_context_menu()` 在 `ContentBrowser.AssetContextMenu` 添加 Send 子菜单
- 入口：`actions.py.on_send_to_photoshop()` → 懒加载 PhotoshopBridge 单例

## 模块 G：外部编辑器桥接（Send to Substance Painter）✅

> 设计文档：[ADR-0004](./decisions/ADR-0004-send-to-substance-painter.md)

### 概述

从 Content Browser 右键选中 StaticMesh，一键发送模型+材质+贴图到 Substance Painter。
与 Module F（Photoshop）不同，SP Bridge 是**跨项目协作**：UE 侧由 AssetCustoms 负责，SP 侧由 SPsync 插件负责。

### 架构

```
AssetCustoms (UE)                              SPsync (SP)
─────────────                                  ──────────
                                               
sp_bridge.py                                   sp_receive.py
├── collect_material_info() → JSON             ├── receive_from_ue(json)
├── export_mesh_fbx() → /tmp/model.fbx        │   ├── project.create(mesh)
├── export_textures() → /tmp/T_*.tga          │   ├── resource.import_project_resource()
└── send_to_sp() ─────HTTP POST──────────────►│   ├── layerstack.insert_fill()
                                               │   ├── fill.set_source(ChannelType, ResourceID)
sp_remote.py (RemotePainter)                   │   └── 配置 export preset
├── base64 encode + HTTP POST → :60041         │
└── 连接检测 + 错误处理                          └── 用户编辑 → sp_sync_export（回传）
```

### 通信方式

- **UE→SP**：HTTP POST base64(python_script) 至 SP Remote Scripting API（localhost:60041）
- **SP→UE**：SPsync 现有链路（Remote Execution TCP 6776）
  - 标准模式：SPSYNCDefault 预设导出 → 新建贴图/材质
  - 回传模式（Round-Trip）：自动检测 metadata → 动态生成导出配置 → 刷新 UE 原贴图

### 已实现文件

| 文件 | 位置 | 职责 |
|------|------|------|
| `sp_bridge.py` | `unreal_integration/` | SPBridge 类：材质收集 + FBX/贴图导出 + 数据包组装（27 tests） |
| `sp_remote.py` | `unreal_integration/` | RemotePainter 类：HTTP 客户端（28 tests） |
| `sp_receive.py` | SPsync 插件目录 | 接收模块：项目创建 + Layer + 通道分配 + 导出预设 + Grayscale Filter + Metadata 存储（24 tests） |
| `sp_channel_map.py` | SPsync 插件目录 | UE↔SP 通道映射 + packed 通道解析 + roundtrip 导出配置生成（31 tests） |

### 关键功能

- **Config Profile Metadata Tag**：导入管线自动写入 `AssetCustoms_ConfigProfile` tag → Send to SP 时读取 → 动态通道映射
- **Per-Material Profile**：多材质槽 SM 每个 MI 独立 Profile → 多 TextureSet 分发 + slot_name 匹配
- **Grayscale Conversion Filter**：Packed Texture (MRO) 在 SP 中自动拆分为独立通道
- **Round-Trip Sync**：SP 项目 Metadata 存储 UE 材质定义 → SYNC 时自动按原格式导出 → 刷新 UE 原贴图

### 依赖

- SP 必须以 `--enable-remote-scripting` 参数启动
- SPsync 插件必须已安装并启用
- AssetCustoms vendor_libs 已部署（PIL 用于贴图格式转换）

### Config Profile Metadata Tag

> 设计文档：[ADR-0005](./decisions/ADR-0005-config-profile-metadata-tag.md)

导入管线在 SM/MI 创建后自动写入 `AssetCustoms_ConfigProfile` metadata tag（值 = Profile 名称如 "Prop"）。Send to SP 时读取 tag → 加载对应 config → 用 `parameter_bindings` 动态生成通道映射，替代硬编码 `sp_channel_map.py`。同时提供 Content Browser 右键菜单查看/编辑/清除 tag，支持旧资产补标。

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
  │       │   ├─ actions.py        # 按钮回调（导入、分诊、Send to PS/SP）
  │       │   ├─ ui.py             # 菜单/工具栏注册
  │       │   ├─ import_pipeline.py # FR2-FR5 导入管线
  │       │   ├─ photoshop_bridge.py # Send to Photoshop (M6)
  │       │   ├─ sp_bridge.py      # Send to Substance Painter (M7)
  │       │   └─ sp_remote.py      # SP HTTP 客户端 (M7)
  │       └─ unreal_qt/            # PySide6 Qt 集成层（详见下方）
  │           ├─ __init__.py       # QApplication 管理 / tick 挂载 / widget 生命周期
  │           └─ dark_bar.py       # 无边框暗色标题栏（DarkBar / FramelessWindow）
  ├─ vendor/                       # 离线 wheel 包（不提交安装产物，仅 .whl）
  │   ├─ pillow-*.whl
  │   ├─ pyside6_essentials-*.whl
  │   ├─ shiboken6-*.whl
  │   ├─ psd_tools-*.whl
  │   ├─ attrs-*.whl
  │   ├─ typing_extensions-*.whl
  │   └─ numpy-*.whl
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
  - **Base_Name 提取策略**（`extract_base_name`）：
    1. 以模型文件名为唯一来源（不从其他信息推导）。
    2. 去扩展名后，剥离已知 UE 前缀（`SM_`/`SK_`/`T_`/`MI_`/`M_`）。
    3. 可读性检测：名称 ≤ 40 字符且不含 UUID 片段（连续 8+ 位 hex）→ 直接使用。
    4. 不可读（AIGC UUID 乱码等）→ 截取原始文件名前 12 字符（不足 12 有几个用几个），去末尾 `_`/`-`。
    5. 后续 SM/MI/贴图名称、目标路径均以此 Base_Name 为基础。
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
  - **资产子目录**：若配置了 `asset_subdirectories`，SM/MI/贴图分别移入对应子目录（如 `Materials/`、`Textures/`）；字段为空则放在 `target_path` 根目录（向后兼容）。
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

## 健壮性与稳定性审计（2026-03-23）

### 审计范围

对全部核心模块（core/、unreal_integration/、unreal_qt/）进行深度代码审查，聚焦：
- 异常处理完整性
- 资源生命周期管理
- 输入校验覆盖度
- 性能隐患
- 静默失败的诊断性

### 已修复问题

| ID | 严重度 | 模块 | 问题 | 修复 |
|----|--------|------|------|------|
| H1 | 高 | `unreal_qt/__init__.py` | tick 定时器永不重置：0.3s 后 `parent_orphan_widgets()` 每帧触发，浪费性能 | 触发后重置 `__timer = 0.0` |
| H2 | 高 | `core/pipeline/standardize.py` | `_load_source_images()` 捕获异常后 `pass`，图片损坏/路径错误完全无日志 | 改为 `logger.warning` 输出 slot、路径、异常信息 |
| H3 | 高 | `unreal_qt/__init__.py` | `widget_manager` 仅有 `add_widget`，窗口关闭后不自动移除引用 → 内存泄漏 | 挂接 `widget.destroyed` 信号自动调用 `remove_widget` |
| H4 | 高 | `import_pipeline.py` | `run_import_pipeline()` 不校验 FBX 文件存在性，直接调用 UE 导入 | 添加 `os.path.isfile()` 前置检查 |
| M1 | 中 | `channel_pack.py` | 重复 `from __future__ import annotations` 语句 | 删除重复行 |
| M2 | 中 | `core/textures/matcher.py` | `discover_texture_files()` 中 `os.listdir()` 未处理 OSError | 添加 `try/except OSError` 跳过不可访问目录 |
| M3 | 中 | `core/pipeline/standardize.py` | `_save_image()` EXR 回退为 PNG 时静默改扩展名 | 添加 `logger.warning` 输出回退信息 |

### 现存风险与建议（低优先级，暂不修复）

| 项目 | 描述 | 建议 |
|------|------|------|
| JSONC 注释剥离 | `_strip_jsonc` 正则对 `//` 的处理是启发式的，可能误删字符串内的 `//` | 典型配置文件不受影响；如需完美支持可安装 `json5` |
| 批量分诊递归深度 | `_show_batch_triage` 用递归回调链式弹出窗口，大量失败时可能栈溢出 | 实际场景极少超过 10 个分诊；如需支持大批量可改为迭代式 |
| 20 项测试跳过 | `test_standardize` 依赖 Pillow 但测试 venv 未安装 | 在 CI/本地测试时执行 `pip install -r requirements-dev.txt` 补全 Pillow |
| `check_texture_mapping` 孤儿策略 | 存在孤儿贴图时标记为 FAILED，可能过于保守 | 当前行为有助于发现遗漏映射，可视需求降级为 WARNING |

### 已有保护机制（确认完好）

| 层级 | 机制 | 状态 |
|------|------|------|
| 管线异常隔离 | `run_import_pipeline` / `resume_after_triage` / `_run_native_embedded_pipeline` 标准化阶段均有 try/except 保护 | ✅ |
| 隔离区保留 | 任何阶段失败都保留隔离区，不执行破坏性清理 | ✅ |
| 性能预算 | `_PERF_BUDGET_SECONDS = 5.0`，超时自动 WARNING | ✅ |
| NFR4 配置校验 | 预设文件不存在时 `os.path.isfile` 拦截并输出诊断信息 | ✅ |
| 批处理异常隔离 | `run_batch_import` 逐文件 try/except，单个失败不阻塞其余 | ✅ |
| 分诊 UI 回调保护 | `_show_triage_ui` 顶层 try/except，弹窗失败不崩溃编辑器 | ✅ |
| 模块分层 | core/ 无 Unreal 依赖，可独立测试；unreal_integration/ 单向依赖 core/ | ✅ |
| 双路径贴图处理 | numpy 快速路径 + Pillow 纯 Python 回退，无 numpy 不崩溃 | ✅ |

## 参考
- 路线图：[docs/roadmap.md](./roadmap.md)
- 需求规格（V1.1）：[./requirements_v1.1.md](./requirements_v1.1.md)
- 编码规范（Google Python）：[../standards/coding-style.md](../standards/coding-style.md)
- ✅ `Tests/test_qt_messagebox.py` 在 UE Editor 中成功弹出 QMessageBox

## 参考
- 路线图：[docs/roadmap.md](./roadmap.md)
- 需求规格（V1.1）：[./requirements_v1.1.md](./requirements_v1.1.md)
- 编码规范（Google Python）：[../standards/coding-style.md](../standards/coding-style.md)

## Config v2.0 三段式管线模型（设计已确认）

> 详见 [ADR-0002](./decisions/ADR-0002-config-v2-pipeline-model.md)

v1.1 的扁平配置结构存在"处理定义"与"交付设置"混杂的问题（`TextureOutputDef` 同时包含 Pillow 通道编排和 UE 导入设置）。v2.0 将配置重构为三段式嵌套：

```
input/          → 识别"什么进来"（贴图匹配规则）
processing/     → 决定"怎么处理"（命名、冲突策略、Pillow 通道编排与格式）
output/         → 描述"怎么交付"（目标路径、子目录、UE 导入设置）
```

**对模块边界的影响**：
- `core/config/schema.py`：`PluginConfig` 拆分为 `InputConfig` + `ProcessingConfig` + `OutputConfig`。
- `core/config/loader.py`：适配嵌套 JSONC 解析。
- `core/naming.py`、`unreal_integration/import_pipeline.py`、`standardize.py`：字段访问路径更新（如 `config.processing.conflict_policy`）。
- `config_editor.py`：Tab 重构为 Input / Processing / Output。
- 删除废弃字段：`texture_merge`、`allowed_modes`（v1.0 遗留，v1.1 已废弃）。

**不变的约束**：依赖方向（`unreal_integration -> core`）、异常隔离策略、隔离区保留策略均不受影响。

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
