# ADR-0004: Send to Substance Painter — 可行性评估与架构决策

| 项目 | 值 |
|------|-----|
| 状态 | **已确认（Accepted）** |
| 日期 | 2026-03-24 |
| 决策者 | 项目负责人 |
| 关联 | `architecture.md`、`roadmap.md`、SPsync 插件 |

---

## 1. 背景与动机

### 1.1 现状

AssetCustoms M6 已实现 **Send to Photoshop**（Content Browser 右键 → 发送 Texture2D 到 PS 编辑 → 自动回写）。
用户希望进一步实现 **Send to Substance Painter**：选中 StaticMesh 后一键发送模型+材质+贴图到 SP，完成贴图创作后自动回传 UE。

### 1.2 涉及项目

| 项目 | 位置 | 角色 |
|------|------|------|
| **AssetCustoms** | `Plugins/AssetCustoms/` (UE 编辑器插件) | UE 侧数据收集、导出、发送 |
| **SPsync** | SP 安装目录 `python/plugins/SPsync/` (SP 插件) | SP 侧接收、项目创建、Layer 操作、回传 |

### 1.3 目标

从 UE Content Browser 右键选中 StaticMesh，一键完成：
1. 导出模型（FBX）、材质信息（JSON）、贴图（TGA/PNG）到临时目录
2. 发送到 Substance Painter 并自动创建项目
3. 自动创建 Fill Layer 并将已有贴图分配到对应通道
4. 配置好导出预设（通道映射匹配 UE 材质定义）
5. 用户在 SP 编辑完成后，通过 SPsync 现有链路自动回传贴图到 UE

---

## 2. 可行性评估（三轮验证）

### 2.1 第一轮：高层可行性（Reference 代码确认）

| 组件 | 参考来源 | 结论 |
|------|----------|------|
| UE 侧材质收集 + FBX 导出 | `Reference/send_tools_sp.py` SPBridge 类 | ✅ 完整实现 |
| HTTP 通信到 SP | `Reference/lib_remote.py` RemotePainter 类 | ✅ base64 POST → localhost:60041 |
| UE 右键菜单注册 | `Reference/init_unreal.py` MenuInitializer | ✅ ContentBrowser.AssetContextMenu |
| SP 项目创建 | `substance_painter.project.create()` API | ✅ 有 API |

### 2.2 第二轮：SP Python API 深度分析（本地源码确认）

从本地安装路径 `C:\Program Files\Adobe\Adobe Substance 3D Painter\resources\python\modules\substance_painter\` 直接读取源码验证。

| 能力 | API | 确认状态 |
|------|-----|----------|
| 创建 Fill Layer | `layerstack.insert_fill(InsertPosition)` | ✅ 返回 `FillLayerNode` |
| 设置活跃通道 | `node.active_channels = {ChannelType.BaseColor, ...}` | ✅ setter 方法 |
| 导入贴图为资源 | `resource.import_project_resource(path, Usage.TEXTURE)` | ✅ 返回 `Resource` |
| 贴图分配到通道 | `node.set_source(ChannelType, ResourceID)` | ✅ `SourceEditorMixin` |
| 添加/配置通道 | `Stack.add_channel(ChannelType, ChannelFormat)` | ✅ |
| 动态导出配置 | `export.export_project_textures(json_config)` | ✅ 完整 JSON 结构 |
| 创建项目 | `project.create(mesh_path, Settings(...))` | ✅ |
| 通道类型枚举 | `textureset.ChannelType.BaseColor/Normal/Metallic/Roughness/AO/Emissive/Opacity/Height` | ✅ 完整覆盖 |

### 2.3 第三轮：新参考工具交叉验证

#### SubstacePainterMCP（社区项目）

- 性质：MCP Server 封装 SP Remote Scripting API
- 通信模式：HTTP POST base64(python) → SP `:60041` → 文件中转结果 (`C:/temp/sp_mcp_result.json`)
- 价值：验证了 HTTP→SP 通道执行 layerstack/textureset Python 代码的完整链路
- 关键代码示例（`server.py` create_fill_layer 工具）：

```python
import substance_painter.layerstack as ls
import substance_painter.textureset as ts

stack = ts.get_active_stack()
position = ls.InsertPosition.from_textureset_stack(stack)
new_layer = ls.insert_fill(position)
new_layer.set_name("LayerName")
```

#### vg_painter_utilities（Adobe 员工 Vincent GAULT 编写）

- 性质：**生产级** SP 插件，Adobe 内部人员代码
- 价值：提供了我们需要的所有 API 的**实际可运行代码**

| 能力 | 代码位置 | 关键用法 |
|------|----------|----------|
| Layer 创建 + 通道选择 | `vg_layerstack.py` `LayerManager.add_layer()` | `insert_fill(pos)` + `active_channels = {getattr(ChannelType, ch)}` |
| 贴图导入为资源 | `vg_export.py` `TextureImporter` | `resource.import_project_resource(path, Usage.TEXTURE)` |
| 贴图分配到通道 | `vg_export.py` `LayerTextureAssigner` | `new_layer.set_source(ChannelType, resource.identifier())` |
| 动态导出配置生成 | `vg_export.py` `ExportConfigGenerator` | 按 channel 动态生成 maps JSON + UDIM 后缀支持 |
| 混合模式设置 | `vg_export.py` `create_layer_from_stack()` | `new_layer.set_blending_mode(BlendingMode(2), channel)` |
| Mask + Generator | `vg_layerstack.py` `MaskManager` | `add_mask(MaskBackground.Black)` + `insert_generator_effect(pos, resource)` |
| 内置资源搜索 | `vg_layerstack.py` | `resource.search("s:starterassets u:generator n:AO")` |
| 颜色源设置 | `vg_layerstack.py` `add_mask_with_fill()` | `fill.set_source(channeltype=None, source=Color(1,1,1))` |
| 通道类型字符串→枚举 | `vg_export.py` `ChannelTypeExtractor` | `getattr(layerstack.ChannelType, channel_string)` |

### 2.4 最终结论

| 核心能力 | 评估级别 | 说明 |
|----------|----------|------|
| SP 理解 UE 材质定义 | ✅✅ 有生产代码 | `getattr(ChannelType, name)` 动态映射 |
| Layer 创建 + 贴图通道链接 | ✅✅ 有完整流水线 | import → create → set_source 三步法 |
| 动态导出配置生成 | ✅✅ 有 UDIM 代码 | ExportConfigGenerator 含 UV Tile 检测 |
| HTTP 通信执行 SP 代码 | ✅✅ MCP 已验证 | base64 POST + 文件中转结果 |
| Mask/Generator/BlendMode | ✅✅ 新增确认 | vg_layerstack 完整示例 |

**整体结论：完全可行**，三大核心问题全部有生产级参考代码。

---

## 3. 通信架构决策

### 3.1 方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A. SP Remote Scripting（推荐）** | UE HTTP POST base64(python) 至 SP `:60041`，SP 执行脚本 | 简单可靠；Reference + MCP 均已验证；SP 内置能力无需额外基础设施 | 需 `--enable-remote-scripting` 启动参数；结果获取需文件中转 |
| B. SPsync 内置 HTTP Server | SPsync 新增 HTTP 端点（如 `:60042`），UE POST JSON 数据 | 逻辑在 SP 侧维护 | 需新开端口；增加 SPsync 复杂度 |
| C. 文件系统监听 | UE 写 JSON + 资产到约定目录，SPsync FileWatcher 检测 | 完全解耦 | 延迟高；不可靠 |

### 3.2 决策

**采用方案 A：SP Remote Scripting 被动接收**。

理由：
1. 与 Reference/lib_remote.py 和 SubstacePainterMCP 一致的模式
2. SP 内置机制，不需要额外基础设施
3. 脚本逻辑（layerstack 操作）作为 **SPsync 的 `sp_receive.py` 模块** 提供维护，AssetCustoms 只负责调用

通信流程：
```
UE (AssetCustoms)                          SP (SPsync)
──────────────                             ─────────
sp_remote.py RemotePainter                 SP Remote Scripting (:60041)
  │                                            │
  ├─ HTTP POST base64(python_script) ────────► │
  │   脚本内容：                                │
  │   from sp_receive import receive_from_ue   │ ← SPsync 模块
  │   receive_from_ue(json_data)               │
  │                                            │
  │                      ◄──────────────────── │ (HTTP 响应 / 文件结果)
```

---

## 4. 跨项目职责划分

### 4.1 完整流程（8 个环节）

```
UE 右键选中 StaticMesh
     │
     ├── ① 收集材质/贴图信息       ─── AssetCustoms
     ├── ② 导出 FBX 到临时目录     ─── AssetCustoms
     ├── ③ 导出贴图到临时目录       ─── AssetCustoms
     ├── ④ HTTP POST 发送到 SP     ─── AssetCustoms
     │
     ├── ⑤ 创建 SP 项目 + 导入网格 ─── SPsync
     ├── ⑥ 创建 Fill Layer + 通道  ─── SPsync
     ├── ⑦ 配置导出预设            ─── SPsync
     └── ⑧ 回传 UE（现有链路）     ─── SPsync（零改动）
```

### 4.2 AssetCustoms 职责（UE 侧：环节 ①②③④）

| 环节 | 新增模块 | 参考代码 | 说明 |
|------|----------|----------|------|
| ① 收集材质信息 | `sp_bridge.py`（新建） | Reference/send_tools_sp.py `_export_material_info()` | 遍历材质槽位 + `get_texture_parameter_names()` 序列化为 JSON |
| ② 导出 FBX | `sp_bridge.py` | Reference/send_tools_sp.py `_export_mesh()` | `StaticMeshExporterFBX` → 临时目录 |
| ③ 导出贴图 | `sp_bridge.py` | Reference/send_tools_sp.py `_export_texture()` | `AssetExportTask` → TGA/PNG |
| ④ HTTP 发送 | `sp_remote.py`（新建） | Reference/lib_remote.py `RemotePainter` | base64 POST 到 SP `:60041` |
| 菜单入口 | `actions.py`（修改） | 现有 `on_send_to_photoshop()` 同模式 | 新增 `on_send_to_substance_painter()` |
| UI 注册 | `ui.py`（修改） | 现有 Send 子菜单 | 新增 "Send to Substance Painter" 菜单项 |

**不需要改动的现有模块**：
- `vendor_libs/`（PIL、PySide6 已有）
- `deploy.ps1`（自动部署系统）
- 现有 import pipeline（FR2-FR5）
- config 系统（JSONC、Schema v2.0）

### 4.3 SPsync 职责（SP 侧：环节 ⑤⑥⑦⑧）

| 环节 | 新增模块 | 参考代码 | 说明 |
|------|----------|----------|------|
| ⑤ 创建项目 + 导入网格 | `sp_receive.py`（新建） | `substance_painter.project.create()` | 解析 JSON 数据 → 创建新项目或重新导入网格 |
| ⑥ 创建 Layer + 通道分配 | `sp_receive.py` | vg_export.py `TextureAssignmentManager` | `import_project_resource()` → `insert_fill()` → `set_source(ChannelType, ResourceID)` |
| ⑦ 配置导出预设 | `sp_receive.py` | vg_export.py `ExportConfigGenerator` | 按 UE 材质定义动态生成 export config（UDIM 支持） |
| ⑧ SP→UE 回传 | **零改动** | `sp_sync_export.py` 现有 `export_end_event()` | 导出触发 → `sync_ue_textures()` → `create_material_and_connect_textures()` |

**可选新增**：
- `sp_channel_map.py`：UE 材质参数名 ↔ SP ChannelType 映射表

### 4.4 UE ↔ SP 通道映射

```python
# UE 材质参数名 → SP ChannelType 枚举名
UE_TO_SP_CHANNEL = {
    "BaseColor":  "BaseColor",
    "Normal":     "Normal",
    "Metallic":   "Metallic",
    "Roughness":  "Roughness",
    "AO":         "AO",           # vg_export 中额外处理 ambientOcclusion→AO
    "Emissive":   "Emissive",
    "Opacity":    "Opacity",
    "Height":     "Height",
}
```

---

## 5. 数据流全景

```
┌─────────────── AssetCustoms (UE) ────────────────────────┐
│                                                           │
│  Content Browser 右键 StaticMesh                          │
│  → actions.on_send_to_substance_painter()                │
│          │                                                │
│    sp_bridge.py                                           │
│    ├── collect_material_info()  →  material_info.json    │
│    ├── export_mesh_fbx()       →  /tmp/model.fbx        │
│    └── export_textures()       →  /tmp/T_*.tga          │
│          │                                                │
│    sp_remote.py (RemotePainter)                           │
│    └── HTTP POST base64(python_script) ──────────┐        │
│                                                  │        │
└──────────────────────────────────────────────────┼────────┘
                                                   │
                  SP Remote Scripting (:60041)      │
                                                   ▼
┌─────────────── SPsync (SP) ──────────────────────────────┐
│                                                           │
│  sp_receive.py                                            │
│  ├── receive_from_ue(json_data)                          │
│  │   ├── project.create(mesh_path, Settings(...))        │
│  │   ├── resource.import_project_resource(tex, TEXTURE)  │
│  │   ├── layerstack.insert_fill(position)                │
│  │   ├── fill.set_source(ChannelType, resource_id)       │
│  │   └── 配置 export preset + 通道映射                    │
│  │                                                        │
│  └── 用户在 SP 中编辑贴图...                               │
│                                                           │
│  ──── 编辑完成 → 导出触发 ────                            │
│                                                           │
│  sp_sync_export.py（现有，零改动）                         │
│  └── export_end_event()                                   │
│      ├── ue_sync.sync_ue_textures()         ─────┐       │
│      └── ue_sync.sync_ue_create_material()  ──┐  │       │
│                                               │  │       │
└───────────────────────────────────────────────┼──┼───────┘
                                                │  │
                  UE Remote Execution (TCP 6776)│  │
                                                ▼  ▼
┌─────────────── UE（现有回传链路）─────────────────────────┐
│  import_textures()                    ← 贴图回传          │
│  create_material_and_connect_textures() ← 材质创建/更新  │
└───────────────────────────────────────────────────────────┘
```

---

## 6. 新增模块清单

### 6.1 AssetCustoms（3 个新文件 + 2 个修改）

```
Content/Python/unreal_integration/
├── sp_bridge.py      # 新建：SPBridge 类（材质收集 + FBX 导出 + 贴图导出 + 数据包组装）
├── sp_remote.py      # 新建：RemotePainter 类（HTTP POST → SP :60041）
├── actions.py        # 修改：新增 on_send_to_substance_painter()
└── ui.py             # 修改：Send 子菜单新增 "Send to Substance Painter"

Content/Python/
└── init_unreal.py    # 可能修改：CONFIG 新增 SP 相关菜单项（若需要）
```

### 6.2 SPsync（1-2 个新文件）

```
SPsync/
├── sp_receive.py       # 新建：接收 UE 数据 → 创建项目 / Layer / 通道分配 / 导出预设
├── sp_channel_map.py   # 新建（可选）：UE 参数名 ↔ SP ChannelType 映射表
└── sp_sync_export.py   # 可能微调：适配 sp_receive 设置的预设
```

---

## 7. 工作量评估

| 端 | 模块 | 复杂度 | 说明 |
|----|------|--------|------|
| AssetCustoms | `sp_remote.py` | **低** | 基本是 Reference/lib_remote.py 的搬运 + 适配 |
| AssetCustoms | `sp_bridge.py` | **中** | 从 Reference/send_tools_sp.py 提取核心逻辑，适配现有架构 |
| AssetCustoms | 菜单 / actions | **低** | 与现有 Send to Photoshop 同模式 |
| SPsync | `sp_receive.py` | **中-高** | **核心新增**：项目创建 + layerstack 操作 + 通道映射 + 导出预设 |
| SPsync | 通道映射 | **低** | UE 参数名→SP ChannelType 字典 |
| 集成 | 端到端测试 | **中** | 需 UE + SP 同时运行 |

**关键路径**：SPsync `sp_receive.py` 是最复杂的新增模块，建议优先开发。

---

## 8. 前置条件与风险

### 8.1 前置条件

| 条件 | 说明 |
|------|------|
| SP 启动参数 | 必须以 `--enable-remote-scripting` 启动 Substance Painter |
| SPsync 已安装 | SP 插件目录中需存在 SPsync 插件 |
| UE Python 环境 | AssetCustoms vendor_libs 已部署（PIL 用于贴图格式转换） |

### 8.2 风险

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| SP 未启用 Remote Scripting | 中 | `sp_remote.py` 添加连接检测 + 用户提示 |
| 大型模型/多材质槽导出慢 | 低 | 可加进度条；贴图按需导出（仅有差异时） |
| SP 版本 API 差异 | 低 | SP 2021.1+ 均支持 Remote Scripting；layerstack API 从 2020.2+ 稳定 |
| UE→SP 通道名映射不全 | 低 | 映射表可扩展；不识别的通道 fallback 为 BaseColor |
| SPsync 回传路径不匹配 | 中 | `sp_receive.py` 创建项目时配置导出路径与 UE Content 路径对齐 |

---

## 9. 备选方案（已拒绝）

| 方案 | 原因 |
|------|------|
| 方案 B：SPsync 内置 HTTP Server | 增加 SPsync 复杂度；需新开端口；SP Remote Scripting 已满足需求 |
| 方案 C：文件系统监听 | 延迟高、不可靠；无法获取执行结果反馈 |
| 引入 MCP 中间层 | 过度工程化；对当前需求无额外价值；直接 HTTP POST 更简单 |
| 全部在 AssetCustoms 中实现 | SP 端 layerstack 操作必须在 SP Python 环境执行，无法在 UE 侧完成 |

---

## 10. 测试策略与任务拆分

### 10.1 测试边界原则

两个项目共享同一规律：**纯 Python 逻辑 = pytest 自动化**；**调用 `unreal` / `substance_painter` 模块 = 必须人工测试**。跨工具 E2E 无已有自动化基础设施，不建议投入自动化。

### 10.2 测试类型定义

| 图标 | 类型 | 环境要求 | 自动化 |
|------|------|----------|--------|
| 🤖 | pytest 自动 | Python 3.11 + venv | ✅ CI 可跑 |
| 👁️ | 人工-UE | UE Editor 运行中 | ❌ |
| 🎨 | 人工-SP | SP 运行中 + `--enable-remote-scripting` | ❌ |
| 🔄 | 人工-E2E | UE + SP 同时运行 | ❌ |

### 10.3 各模块测试能力分析

**AssetCustoms 侧（可自动化 ~40%）**

| 模块 | 可自动化 (🤖) | 必须人工 |
|------|---------------|----------|
| `sp_remote.py` | base64 编码、HTTP 错误处理（mock urllib）、连接检测逻辑 | 实际 HTTP→SP 连通性 (🎨) |
| `sp_bridge.py` | material_info JSON 序列化/反序列化、数据包组装 | collect_material_info / export_mesh / export_textures (👁️) |
| `actions.py` / `ui.py` | — | 菜单注册、点击触发 (👁️) |

**SPsync 侧（可自动化 ~35%）**

| 模块 | 可自动化 (🤖) | 必须人工 |
|------|---------------|----------|
| `sp_channel_map.py` | 映射字典全部逻辑、fallback、边界用例 | — |
| `sp_receive.py` | JSON 数据包解析/校验、导出配置 JSON 生成 | project.create / layerstack / resource 操作 (🎨) |

### 10.4 细化任务拆分（含测试标注）

**Phase 1：AssetCustoms UE 侧**

| ID | Step | 子任务 | 测试 | 说明 |
|----|------|--------|------|------|
| 1.1 | 1 | `encode_script()` base64 编码函数 | 🤖 | 纯函数，输入字符串→输出 base64 |
| 1.2 | 1 | `RemotePainter.execute()` HTTP POST 封装 | 🤖 | mock `urllib.request`，验证请求格式 |
| 1.3 | 1 | 连接检测 + SP 未启动错误处理 | 🤖 | mock 超时/refused，验证异常路径 |
| 1.4 | 1 | 实际 SP 连通性验证 | 🎨 | SP 运行中执行 ping 脚本 |
| 2.1 | 2 | material_info JSON schema + 序列化/反序列化 | 🤖 | 定义数据结构，round-trip 测试 |
| 2.2 | 2 | `collect_material_info()` 材质槽遍历 | 👁️ | 用测试 SM 验证产出 JSON 正确 |
| 2.3 | 2 | `export_mesh_fbx()` FBX 导出 | 👁️ | 验证输出文件存在且可被 SP 打开 |
| 2.4 | 2 | `export_textures()` 贴图导出 | 👁️ | 验证 TGA/PNG 输出到临时目录 |
| 2.5 | 2 | `send_to_sp()` 数据包组装 | 🤖 | 纯打包逻辑（给定 material_info → 脚本字符串） |
| 2.6 | 2 | `send_to_sp()` 实际发送 | 🔄 | SP 运行中完整发送验证 |
| 3.1 | 3 | `on_send_to_substance_painter()` action | 👁️ | 右键菜单可见 + 点击触发 |
| 3.2 | 3 | UI 子菜单项叠加验证 | 👁️ | 不影响现有 Send to PS 菜单 |

**Phase 2：SPsync SP 侧**

| ID | Step | 子任务 | 测试 | 说明 |
|----|------|--------|------|------|
| 4.1 | 4 | JSON 数据包解析 + 入参校验 | 🤖 | 纯 Python，验证必填字段/类型/缺失处理 |
| 4.2 | 4 | 导出配置 JSON 生成函数 | 🤖 | 给定通道列表→生成 export config dict |
| 4.3 | 4 | `project.create()` 创建项目 + 网格导入 | 🎨 | SP 中执行，验证项目创建成功 |
| 4.4 | 4 | `resource.import_project_resource()` 贴图导入 | 🎨 | 验证贴图出现在 SP shelf |
| 4.5 | 4 | `insert_fill()` + `set_source()` 通道分配 | 🎨 | 验证 Layer 创建且贴图正确链接 |
| 4.6 | 4 | 导出预设配置应用 | 🎨 | 验证导出设置面板配置正确 |
| 5.1 | 5 | 通道映射字典 + fallback 逻辑 | 🤖 | 已知通道+未知通道+大小写 |
| 5.2 | 5 | 多材质槽 / UDIM 映射场景 | 🤖 | 边界用例 |

**Phase 3：集成与回传**

| ID | Step | 子任务 | 测试 | 说明 |
|----|------|--------|------|------|
| 6.1 | 6 | 回传链路 `export_end_event()` → `sync_ue_textures()` | 🔄 | 确认现有链路不因新模块受影响 |
| 6.2 | 6 | 导出路径与 UE Content 路径对齐 | 🔄 | 确认贴图落入正确目录 |
| 7.1 | 7 | 完整主链路 E2E | 🔄 | UE 右键→SP 项目→Layer→编辑→导出→UE |
| 7.2 | 7 | 回传贴图格式 / 命名 / 材质绑定 | 🔄 | 验证 MI 参数正确 |
| 7.3 | 7 | 异常场景矩阵 | 🔄 | SP 未启动 / SM 无材质 / 多材质槽 / UDIM |

### 10.5 统计

| 测试类型 | 数量 | 占比 |
|----------|------|------|
| 🤖 pytest 自动 | 10 | 40% |
| 👁️ 人工-UE | 5 | 20% |
| 🎨 人工-SP | 5 | 20% |
| 🔄 人工-E2E | 5 | 20% |
| **合计** | **25** | 100% |

### 10.6 建议开发与测试顺序

```
① 纯逻辑先行 (🤖)      ─ 1.1-1.3, 2.1, 2.5, 4.1-4.2, 5.1-5.2
      │                   建立测试安全网，可反复回归
      ▼
② UE 侧人工 (👁️)       ─ 2.2-2.4, 3.1-3.2
      │                   UE Editor 内验证数据收集 + 导出
      ▼
③ SP 侧人工 (🎨)        ─ 1.4, 4.3-4.6
      │                   SP 内验证项目创建 + Layer 操作
      ▼
④ 跨工具 E2E (🔄)       ─ 2.6, 6.1-6.2, 7.1-7.3
                          双工具联调，最后执行
```

**理由**：先建立可反复运行的 pytest 安全网，再逐步扩展到需要人工操作的环境。跨工具 E2E 留到最后，因为它依赖两侧各自独立验证通过。

---

## 11. 参考资料

| 资料 | 位置 | 说明 |
|------|------|------|
| SPBridge 参考实现 | `Reference/send_tools_sp.py` | UE→SP 完整导出流程 |
| RemotePainter 参考 | `Reference/lib_remote.py` | HTTP 通信客户端 |
| 材质模板 | `Reference/environment_material_template.json` | 通道映射定义示例 |
| SubstacePainterMCP | `Reference/SubstacePainterMCP-main/` | MCP Server + layerstack 操作验证 |
| vg_painter_utilities | `Reference/vg_painter_utilities-main/` | Adobe 员工生产级 layerstack/export 代码 |
| SP Python API 源码 | `C:\Program Files\Adobe\...\substance_painter\` | layerstack/resource/export/textureset 模块 |
| SPsync 插件 | SP 安装目录 `python/plugins/SPsync/` | 现有 SP→UE 回传链路 |
