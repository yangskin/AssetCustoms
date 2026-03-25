# ADR-0005: Config Profile Metadata Tag — 配置驱动的资产标签与通道映射

| 项目 | 值 |
|------|-----|
| 状态 | **计划中（Proposed）** |
| 日期 | 2026-03-25 |
| 决策者 | 项目负责人 |
| 关联 | `ADR-0004`（Send to SP）、`roadmap.md`、`Prop.jsonc` |

---

## 1. 背景与动机

### 1.1 现状

M7 Send to Substance Painter 已打通全链路（UE→SP 模型+贴图+Fill Layer+通道分配），但存在两个缺陷：

1. **通道映射硬编码**：`sp_channel_map.py` 使用静态字典 `UE_TO_SP_CHANNEL` 将 UE 材质参数名映射到 SP ChannelType。新增 Profile（如 Character）或不同 `parameter_bindings` 时必须手动更新代码。
2. **资产与 Profile 脱节**：导入时使用的 Profile（如 "Prop"）仅作为参数传入管线，**不持久化到资产上**。后续操作（Send to SP、配置查询等）无法知道某个 SM/MI 是用哪个 Profile 创建的。

### 1.2 目标

1. 导入管线自动在生成的 SM/MI 上打标签，记录所用 Profile。
2. 提供 Content Browser 右键菜单，查看/修改/清除资产的 Profile 标签。
3. Send to SP 时读取标签 → 加载对应 Profile 配置 → 用 `parameter_bindings` 动态生成通道映射，替代硬编码。

---

## 2. 技术方案

### 2.1 存储机制：UE Metadata Tag

采用 `UPackage::MetaData` 原生机制（已在 ADR-0004 可行性调研中确认）：

| API | 用途 |
|-----|------|
| `EditorAssetLibrary.set_metadata_tag(obj, tag, value)` | 写入标签 |
| `EditorAssetLibrary.get_metadata_tag(obj, tag)` | 读取标签 |
| `EditorAssetLibrary.remove_metadata_tag(obj, tag)` | 删除标签 |
| `EditorAssetLibrary.get_tag_values(asset_path)` | 无需加载即可读取所有标签 |

- **标签名**：`AssetCustoms_ConfigProfile`
- **标签值**：Profile 名称（如 `"Prop"`、`"Character"`）
- **持久化**：随 uasset 文件保存，Editor-only（`WITH_EDITORONLY_DATA`）

### 2.2 UE 内置 UI 调查结论

**UE 没有内置 UI 查看/编辑自定义 metadata tag**：
- Asset Details Panel：仅展示 UPROPERTY 反射属性
- Asset Audit Window：展示 Asset Registry Tags（引擎级），不含自定义 `UPackage::MetaData`
- Property Matrix：同 Details Panel，仅展示反射属性

因此需要自建右键菜单 UI。

---

## 3. 三步实施计划

### Step 1：导入管线打标签（低复杂度）

**改动范围**：`import_pipeline.py`

在两条管线路径的 MI/SM 创建并保存后，追加 `set_metadata_tag` 调用：

```python
# 在 MI 和 SM 创建保存后
EditorAssetLibrary.set_metadata_tag(mi, "AssetCustoms_ConfigProfile", category)
EditorAssetLibrary.set_metadata_tag(sm, "AssetCustoms_ConfigProfile", category)
```

**插入点**：
- `run_import_pipeline()`：Step 5.7（MIC 创建）之后、Step 5.8（SM→MI 绑定）之后
- `_run_native_embedded_pipeline()`：Step 8（MI 创建+链接）之后、Step 9（SM→MI 绑定）之后

**前置条件**：
- `category` 参数已在两个函数签名中作为入参存在，**零额外输入**
- `UnrealAssetOps` 需新增 `set_metadata_tag()` 方法封装

**测试**：
- 🤖 pytest：mock `EditorAssetLibrary.set_metadata_tag` 验证调用参数
- 👁️ 人工-UE：导入后用 Python 命令 `EditorAssetLibrary.get_metadata_tag()` 确认标签存在

### Step 2：Content Browser 右键菜单查看/编辑 Profile（中复杂度）

**改动范围**：`ui.py`、`actions.py`

复用现有 `ContentBrowser.AssetContextMenu` 注册模式（与 Send to PS / Send to SP 同架构），新增子菜单：

```
右键资产 → AssetCustoms ▸
  ├── Send ▸
  │   ├── Send to Photoshop
  │   └── Send to Substance Painter
  └── Config Profile ▸
      ├── View Profile          ← 读取 tag 并显示
      ├── Set Profile ▸         ← 动态列出可用 Profile，选中后写入
      │   ├── Prop
      │   ├── Character
      │   └── ...（从 Config 目录扫描）
      └── Clear Profile         ← 删除 tag
```

**实现要点**：
- `actions.py`：新增 `on_view_config_profile()`、`on_set_config_profile(profile_name)`、`on_clear_config_profile()`
- "View" 使用 `unreal.EditorDialog.show_message()` 显示当前值（无需 PySide6）
- "Set" 通过 `set_metadata_tag` 写入 + `save_asset` 持久化
- "Clear" 通过 `remove_metadata_tag` 删除
- Profile 列表从 `Content/Config/AssetCustoms/*.jsonc` 动态扫描（复用现有 Profile 扫描逻辑）
- 支持多选资产批量操作

**测试**：
- 👁️ 人工-UE：菜单可见性、View 弹窗内容、Set 写入验证、Clear 删除验证、多选批量

### Step 3：SP 发送配置驱动映射（中复杂度）

**改动范围**：`sp_bridge.py`（UE 侧）、`sp_receive.py`（SP 侧）、`sp_channel_map.py`（SP 侧）

#### 3a. UE 侧：读取 tag + 注入 config 到数据包

在 `_collect_material_info()` 中追加 tag 读取：

```python
profile = EditorAssetLibrary.get_metadata_tag(static_mesh, "AssetCustoms_ConfigProfile")
if not profile:
    # 弹窗提示用户先设置 Profile，或 fallback
    ...
```

将 `parameter_bindings` 注入到发送给 SP 的 JSON 数据包中：

```json
{
  "mesh_name": "SM_MyProp",
  "config_profile": "Prop",
  "parameter_bindings": {
    "D": "BaseColor_Texture",
    "N": "Normal_Texture",
    "MRO": "Packed_Texture",
    "H": "Height_Texture"
  },
  "materials": [...]
}
```

#### 3b. SP 侧：配置驱动映射

`sp_receive.py` / `sp_channel_map.py` 利用收到的 `parameter_bindings` 构建反向映射：

```python
# parameter_bindings: {"D": "BaseColor_Texture", "N": "Normal_Texture", ...}
# texture_definitions (从 config): suffix "D" → channels from "BaseColor"
# 结果：UE param "BaseColor_Texture" → SP channel "BaseColor"
#        UE param "Normal_Texture"    → SP channel "Normal"
#        UE param "Packed_Texture"    → SP channel "Roughness"（packed 特殊处理）
```

当 JSON 数据包中包含 `parameter_bindings` 时，使用配置驱动映射；不包含时 fallback 到现有 `UE_TO_SP_CHANNEL` 硬编码映射（向后兼容）。

**测试**：
- 🤖 pytest：配置驱动映射生成逻辑、fallback 逻辑、缺失 tag 处理
- 🔄 人工-E2E：带 tag 的 SM 发送到 SP，验证通道分配正确

---

## 4. 依赖关系与执行顺序

```
Step 1（打标签）── 独立，可先实施
     │
     ├─► Step 2（右键菜单）── 依赖 Step 1 的 tag 存在
     │
     └─► Step 3（SP 配置驱动）── 依赖 Step 1 的 tag + Step 2 的补标能力
```

**建议顺序**：Step 1 → Step 2 → Step 3

Step 1 和 Step 2 可在 M7 Phase 3（集成）中完成。Step 3 可作为 M7 的收尾优化。

---

## 5. 风险与缓解

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 旧资产无 tag | 低 | Step 2 "Set Profile" 可补标；Step 3 无 tag 时 fallback 到硬编码映射 |
| tag 值与 config 文件不匹配 | 低 | 发送时校验 config 文件存在性，不存在则提示用户 |
| 多材质槽使用不同 Profile | 极低 | 当前管线每个 SM 只用一个 Profile，暂不支持混合 |
| 性能：tag 读写开销 | 极低 | `set/get_metadata_tag` 是内存操作，仅 `save_asset` 时写盘 |

---

## 6. 备选方案（已拒绝）

| 方案 | 原因 |
|------|------|
| `AssetUserData` 子类 | 需 C++ 定义子类，Python-only 工具链不适合 |
| Asset Registry 自定义 Tag | 需 C++ `GetAssetRegistryTags()` override |
| 配置名写入资产文件名 | 侵入命名规范，无法修改 |
| 外部数据库/JSON 映射表 | 与资产脱节，移动/复制资产后失效 |
