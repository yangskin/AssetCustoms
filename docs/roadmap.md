# 路线图 / 里程碑（V1.4）

版本: V1.4（Texture Size Control + Resolution Authority）  |  状态: M9 已完成  |  负责人: （您的名字/TA团队）  |  最后更新: 2026-03-26

本文件用于跟踪项目阶段性目标与关键里程碑，确保对齐产品价值与技术落地节奏。

## 愿景（Product Vision）
AssetCustoms 是 Unreal Engine 编辑器插件，定位为项目资产管线的“标准化守门员”。
它将非生产就绪的外部“数字毛坯”资产，通过 TA 配置的自动化工作流实现“静默成功，响亮失败”的一键转化，生成符合规范的生产就绪资产。

V1.1 核心目标：在多管线（角色/场景等）下，100% 自动化完成命名、PBR 贴图打包、材质实例（MIC）创建与贴图导入设置。

## 目标用户与用户故事（摘要）
- 主要用户：美术（场景/角色/道具）、关卡设计师。
	- 故事：10 秒内把外部模型以“Prop”规范导入，自动重命名、打包 MRO、创建 MI、设置法线压缩。
- 次要用户：技术美术（TA）。
	- 故事：为不同管线（Character / Prop）创建独立 Profile 配置文件，美术只需选择 Profile 即可执行完整规则。

## M1 — 文档与规范（完成）
- [x] 建立文档骨架与索引（README, docs, standards）
- [x] 采用 Conventional Commits
- [x] Code Review 检查单与编码规范（Google Python 规范）
- [x] ADR-0001：采用文档与流程规范

## M2 — V1.1 功能落地 ✅（已完成）
- [x] FR1：TA 配置系统（JSONC、Profile 扫描/加载、Schema v1.1）✅
	- 进度（2026-03-22）：
		- [x] JSONC 解析能力完成（优先 json5，回退注释剥离+尾逗号处理）。
		- [x] `Content/Config/AssetCustoms/Prop.jsonc` 默认 Profile 提供。
		- [x] `core.config.loader.load_config()` 输出数据类 `PluginConfig`（当前覆盖：texture_merge、allowed_modes）。
		- [x] Unreal 侧 Profile 扫描与下拉菜单项生成（Content/Config/AssetCustoms/*.jsonc）。
		- [x] Schema v1.1 全量字段适配（9 dataclass，23 项测试通过）。
- [x] FR2：智能导入核心流程 ✅
	- [x] Content Browser 工具栏下拉（动态 Profile 列表）
	- [x] tkinter 文件对话框（仅 .fbx）+ Content Browser 路径采样
	- [x] ImportContext 构建（解析 Profile + 采样路径）
	- [x] 隔离区路径计算 `core/naming.py`
	- [x] 导入管道编排 `unreal_integration/import_pipeline.py`
- [x] FR2.5：原生嵌入贴图管线 ✅（新增 2026-03-22）
	- [x] 三层匹配策略：名称 pattern → sRGB 启发式 → 单贴图兜底 BaseColor
	- [x] 跳过 Pillow，直接操作 UE 资产（重命名 + 导入设置）
	- [x] 内部贴图优先：Phase 3.5 无条件覆盖，FBX 嵌入贴图始终优先于外部匹配
	- [x] 自动材质绑定读取：`read_material_texture_bindings()` 从 FBX 自动材质（MIC）读取 `texture_parameter_values`
	- [x] `FBX_PARAM_TO_SLOT` 映射表（DiffuseColorMap→BaseColor 等 8 项）
	- [x] `_is_direct_passthrough()` 嵌入贴图直通路径
- [x] FR3：自动化检查链 ✅
	- [x] 贴图匹配引擎 `core/textures/matcher.py`（glob/regex + priority）
	- [x] 检查链 `core/pipeline/check_chain.py`（资产数量 + 材质 + 映射完整性）
	- [x] 支持 allow_missing + constant 兜底
- [x] FR4：分诊 UI ✅（2026-03-22 实现 + 视觉验证通过）
	- 进度（2026-03-22）：
		- [x] PySide6-Essentials 6.10.2 + shiboken6 6.10.2 离线 wheel 已入 vendor/
		- [x] deploy.ps1 支持 PySide6 安装/清理/验证
		- [x] `unreal_qt` 模块适配 PySide6（移除 PySide2 兼容）
		- [x] QMessageBox 集成测试通过（`Tests/test_qt_messagebox.py`）
		- [x] `core/pipeline/triage_ui.py`：TriageWindow + TriageDecision 数据模型
		  - 错误标题（红色 ✖ badge）、BaseName 编辑框
		  - 贴图映射表（QTableWidget + QComboBox，状态：✔已匹配/✖未匹配/⚠歧义）
		  - 孤儿贴图提示、执行/取消按钮、UE 暗色主题
		- [x] `import_pipeline.py`：TriageContext + resume_after_triage()（修正映射后继续 FR5）
		- [x] `actions.py`：_show_triage_ui() 集成（FR3 失败自动弹出）
		- [x] 8 项单元测试 + UE 编辑器内视觉验证通过
- [x] FR5：标准化执行引擎 ✅
	- [x] 5.1 贴图处理（Pillow 通道编排 + flip_green + resize + 保存）
	- [x] 5.2 资产重命名/移动
	- [x] 5.3 MIC 创建/链接
	- [x] 5.4 SM→MI 绑定：`mesh.set_material(slot, mi)`（2026-03-22 修复 `set_editor_property` 值类型写回失效问题）
	- [x] 5.5 隔离区清理
	- [x] 5.6 导入设置应用
	- [x] 5.7 MM_Prop_PBR 母材质（2026-03-22 通过 MCP 创建）：
		- `BaseColor_Texture`(Color) → BaseColor
		- `Normal_Texture`(Normal) → Normal
		- `Packed_Texture`(LinearColor) → Metallic(R) / Roughness(G) / AO(B)
		- `Height_Texture`(LinearColor) → 预留

## M3 — 质量与体验 ✅（已完成）
- [x] 性能预算：典型资产"静默成功"全流程 ≤ 5s（NFR1）✅
	- 进度（2026-03-22）：
		- [x] `run_import_pipeline()` 和 `resume_after_triage()` 添加 `time.monotonic()` 计时器
		- [x] 成功时日志报告耗时；超出 5s 阈值输出 WARNING
		- [x] 性能常量 `_PERF_BUDGET_SECONDS = 5.0`
- [x] 健壮性：失败停止在"隔离区"，编辑器不崩溃（NFR3）✅
	- 进度（2026-03-22）：
		- [x] `run_import_pipeline()` 标准化阶段 try/except 保护：异常记录日志并保留隔离区
		- [x] `resume_after_triage()` 标准化阶段 try/except 保护：同上
		- [x] `_run_native_embedded_pipeline()` 步骤 6-10 try/except 保护：同上
		- [x] `export_texture_to_disk()` 失败时补充 WARNING 日志
		- [x] 外层 `actions.py` 的 `on_pick_fbx_with_preset()` + `_show_triage_ui.on_accept()` 已有顶级 try/except
- [x] 未找到配置时 UI 提示并禁用入口（NFR4）✅
	- 进度（2026-03-22）：
		- [x] `ui.py`：无配置占位项改为"⚠ 配置缺失 (Config Missing)" + Icons.Error + log_error
		- [x] `actions.py`：`on_pick_fbx_with_preset()` 添加 `os.path.isfile` 前置检查

## M4 — 批处理 ✅（已完成 2026-03-23）
- [x] 批量 FBX 导入：文件对话框多选 → 逐个执行管线 → 汇总结果
- [x] 分诊排队：检查失败的文件缓存结果，批处理结束后逐个弹出分诊 UI

## 健壮性审计 ✅（2026-03-23）
- [x] 深度代码审查：core/、unreal_integration/、unreal_qt/ 全量审计
- [x] 修复 7 项问题（4 高 + 3 中）：
  - [x] H1: `unreal_qt` tick 定时器不重置 → 每帧运行 parent_orphan_widgets
  - [x] H2: `_load_source_images` 静默吞异常 → 图片损坏无法诊断
  - [x] H3: `widget_manager` 无自动清理 → 窗口关闭后内存泄漏
  - [x] H4: `run_import_pipeline` 不校验 FBX 文件存在性
  - [x] M1: `channel_pack.py` 重复 import 语句
  - [x] M2: `discover_texture_files` 不可访问目录无保护
  - [x] M3: `_save_image` EXR 回退静默改扩展名
- [x] 确认已有保护机制完好（管线异常隔离、隔离区保留、性能预算、批处理隔离等）
- [x] 文档同步：architecture.md 新增审计章节、testing.md 更新测试状态、roadmap.md 更新

## M5 — Config v2.0 三段式管线模型 ✅（已完成 2026-03-23）

> 设计文档：[ADR-0002](./decisions/ADR-0002-config-v2-pipeline-model.md)（状态：已确认）

**目标**：将扁平的 v1.1 配置重构为 Input → Processing → Output 三段式嵌套结构，消除"处理定义"与"交付设置"混杂的问题：
- `input`：贴图识别规则（`texture_rules`），Mesh/Material 仅注释占位。
- `processing`：冲突策略、Mesh 导入设置、贴图处理定义（Pillow 通道编排 + format/bit_depth/srgb/mips）。
- `output`：目标路径、子目录、命名模板、材质绑定、导入设置默认值、逐贴图 import override（集中表格）。

**关键决策**（Q1-Q6 已确认）：
- `format`/`bit_depth`/`srgb`/`mips` 保留在 `processing`
- `conflict_policy` 保留在 `processing`
- `parameter_bindings` 以 `suffix` 为 key
- `texture_merge`/`allowed_modes` 直接删除
- `input.mesh`/`input.material` 暂留注释占位
- `texture_import_overrides` 采用 Output Tab 集中表格（方案 A）

**实施计划**（5 步全部完成）：
- [x] Step 1：Schema + Loader 重写（`schema.py` → `InputConfig`/`ProcessingConfig`/`OutputConfig` 三层嵌套，`loader.py` 适配）
- [x] Step 2：JSONC 模板迁移（`Prop.jsonc`、`Character.jsonc` → v2.0 结构，`config_version: "2.0"`）
- [x] Step 3：管线代码适配（`naming.py`、`import_pipeline.py`、`standardize.py` 全部使用 v2.0 字段路径）
- [x] Step 4：Config Editor UI 重构（3 Tab：Input / Processing / Output，含双语支持）
- [x] Step 5：测试 & 回归（90 tests: 70 passed, 20 skipped + E2E 验证通过）

## M6 — Send to Photoshop ✅（已完成 2026-03-23）

**目标**：从 Content Browser 右键将 Texture2D 发送到 Photoshop 编辑，保存后自动回写 UE。

**实现**：
- [x] `unreal_integration/photoshop_bridge.py`：PhotoshopBridge 主类 + TickTimer/TextureMonitor 文件监控
- [x] `ui.py`：`_register_asset_context_menu()` 在 `ContentBrowser.AssetContextMenu` 注册 Send > Send to Photoshop
- [x] `actions.py`：`on_send_to_photoshop()` 懒加载 PhotoshopBridge 单例
- [x] 入口 `init_unreal.py` 未修改，注册通过 `register_all()` 自动完成
- [x] 新增依赖：psd-tools（离线 wheel + deploy.ps1 更新）

**功能流程**：
1. 选中 Texture2D → 右键 → Send → Send to Photoshop
2. 导出为 TGA → 转换为 PSD → 启动 Photoshop 打开
3. TextureMonitor（1s 轮询）检测 PSD 修改 → 自动重新导入（保留 sRGB/压缩/LOD 设置）
4. Photoshop 关闭后自动清理临时文件（TGA + PSD）

## M7 — Send to Substance Painter ✅（已完成 2026-03-25）

> 设计文档：[ADR-0004](./decisions/ADR-0004-send-to-substance-painter.md)（状态：已确认）
> 可行性评估：三轮验证完成（Reference 代码 + SP API 源码 + 生产级参考工具）

**目标**：从 Content Browser 右键选中 StaticMesh，一键发送模型+材质+贴图到 Substance Painter，完成贴图创作后自动回传 UE。

**跨项目协作**：AssetCustoms（UE 侧发送）+ SPsync（SP 侧接收+回传）

### Phase 1：AssetCustoms UE 侧（发送端）

> 测试标注：🤖 pytest 自动 | 👁️ 人工-UE | 🎨 人工-SP | 🔄 人工-E2E

- [x] Step 1：`sp_remote.py` — RemotePainter HTTP 客户端（28 tests）
  - 从 Reference/lib_remote.py 移入正式代码
  - base64 编码 + HTTP POST → SP `:60041`
  - 连接检测 + 未连接时用户友好提示
  - 测试：🤖 base64 编码 / HTTP mock / 错误处理 → 🎨 实际 SP 连通性
- [x] Step 2：`sp_bridge.py` — SPBridge 主类（27 tests）
  - `collect_material_info()` — 遍历 StaticMesh 材质槽位 + 贴图参数 → JSON
  - `export_mesh_fbx()` — StaticMeshExporterFBX → 临时目录
  - `export_textures()` — AssetExportTask → TGA/PNG
  - `send_to_sp()` — 打包数据 + 调用 RemotePainter 执行 SP 端脚本
  - 测试：🤖 JSON schema / 序列化 / 数据包组装 → 👁️ UE API 导出 → 🔄 实际发送
- [x] Step 3：菜单注册 + actions 集成 ✅
  - `ui.py`：Send 子菜单新增 "Send to Substance Painter"
  - `actions.py`：新增 `on_send_to_substance_painter()` 懒加载 SPBridge 单例
  - 测试：👁️ 菜单可见 + 点击触发 + 不影响现有菜单

### Phase 2：SPsync SP 侧（接收端）

- [x] Step 4：`sp_receive.py` — 接收模块（24 tests）
  - `receive_from_ue(json_data)` — 解析 UE 数据包
  - 创建 SP 项目：`project.create(mesh_path, Settings(...))`
  - 导入贴图：`resource.import_project_resource(path, Usage.TEXTURE)`
  - 创建 Fill Layer：`layerstack.insert_fill(position)`
  - 通道分配：`fill.set_source(ChannelType, resource_id)`
  - 配置导出预设：动态生成 export config JSON
  - 测试：🤖 JSON 解析 / 校验 / 导出配置生成 → 🎨 SP 内 layerstack 全链路
- [x] Step 5：`sp_channel_map.py`（31 tests）
  - UE 材质参数名 ↔ SP ChannelType 映射字典 + `_Texture` 后缀 + packed 映射
  - 测试：🤖 31 passed

### Phase 3：集成与回传

- [x] Step 6：回传链路验证 ✅
  - SPsync 事件驱动架构（ProjectEditionEntered 回调），全链路已打通
  - 9 个运行时问题已修复（详见 .ai-context/current-task.md）
- [ ] Step 7：端到端测试（待人工验证）

### Phase 4：Config Profile Metadata Tag ✅（2026-03-25）

> 设计文档：[ADR-0005](./decisions/ADR-0005-config-profile-metadata-tag.md)

- [x] Step 8：导入管线打标签（3 条路径）
  - 标准化管线 / 分诊恢复 / 原生嵌入管线完成后自动写入 `AssetCustoms_ConfigProfile` metadata tag
- [x] Step 9：右键菜单 View/Set/Clear
  - Content Browser 右键菜单支持查看/设置/清除 metadata tag
- [x] Step 10：SP 发送配置驱动映射
  - Send to SP 时读取 tag → 加载 config → 用 `parameter_bindings` 动态生成通道映射
- 测试：AssetCustoms 56 passed, SPsync 122 passed

### Phase 5：Per-Material Profile + 多 TextureSet ✅（2026-03-25）

- [x] Step 11：per-MI tag 读取 + `material_slot_name` 注入数据包
- [x] Step 12：`all_texture_sets()` 多 TextureSet 分发 + slot_name 优先匹配
- [x] Step 13：`match_material_to_textureset(mat_name, ts_names, slot_name)` 5 级策略
  - 关键修正：匹配关系从 MI 名→TextureSet 改为 slot_name→TextureSet
- 测试：AssetCustoms 56 passed, SPsync 139 passed (+17 新增)

### Phase 6：Grayscale Conversion Filter 通道拆分 ✅（2026-03-25）

- [x] Step 15a：`parse_channel_suffix()` + `resolve_packed_channels()`（sp_channel_map.py）
- [x] Step 15b：`_find_grayscale_filter()` + `_create_fill_with_filter()`（sp_receive.py）
  - 重写为 per-channel source 方式，支持 Packed Texture MRO 在 SP 中自动拆分
- [x] Bug Fix：Config 文件通道后缀格式更新（Prop.jsonc, Character.jsonc）
- [x] Bug Fix：`extract_channels_from_materials()` 打包通道展开
- 测试：SPsync 162 passed, AssetCustoms core 103 passed

### Round-Trip Sync（SP → UE 贴图回传）✅（2026-03-25）

> 设计文档：[ROUNDTRIP_SYNC.md](SPsync/doc/ROUNDTRIP_SYNC.md)

- [x] 5A：`build_roundtrip_metadata()` — SP 项目元数据存储 UE 材质定义
- [x] 5B：`build_roundtrip_export_maps/config/refresh_list()` — 动态导出配置生成
- [x] 5C：`refresh_textures()` + `sync_ue_refresh_textures()` — UE 侧按原路径刷新
- [x] 5D：`sp_sync_export.py` roundtrip 模式集成（自动检测元数据）
- [x] Bug Fix：rootPath mismatch → `texture_set_name` 三层 fallback
- [x] Bug Fix：Bootstrap `.py` + button lock + logging + UI path（4 处）
- [x] Bug Fix：BaseColor 导出黑色 → `srcMapName`/`srcChannel` 格式改用 ChannelType 名
- [x] Bug Fix：AO srcMapName "ao" → "ambientOcclusion"（probe 脚本验证）
- [x] Bug Fix：标准导出 metallic 异常 → `sync_textures(roundtrip=False)` 跳过自动检测
- [x] Bug Fix：Emissive BCO fallback → 材质实例仅在 `emissive_type=True` 时设置 ES 参数
- 测试：SPsync 191 passed
  - UE 右键发送 → SP 创建项目 + Layer → 编辑 → 导出 → 自动回传 UE
  - 验证回传贴图格式、命名、材质绑定
  - 测试：🔄 完整主链路 + 异常场景矩阵（SP 未启动 / SM 无材质 / 多材质槽 / UDIM）

### 测试统计

| 类型 | 数量 | 占比 |
|------|------|------|
| 🤖 pytest 自动 | 10 | 40% |
| 👁️ 人工-UE | 5 | 20% |
| 🎨 人工-SP | 5 | 20% |
| 🔄 人工-E2E | 5 | 20% |

**开发顺序建议**：① 纯逻辑 + pytest → ② UE 侧人工 → ③ SP 侧人工 → ④ 跨工具 E2E

> 详细任务拆分（25 项子任务 + 测试标注）见 [ADR-0004 §10](./decisions/ADR-0004-send-to-substance-painter.md#104-细化任务拆分含测试标注)

### Phase 4：Config Profile 元数据标签（配置驱动映射）

> 设计文档：[ADR-0005](./decisions/ADR-0005-config-profile-metadata-tag.md)（状态：计划中）

**目标**：通过 UE Metadata Tag 将 Profile 信息持久化到资产上，实现配置驱动的通道映射，替代 `sp_channel_map.py` 硬编码。

- [x] Step 8：导入管线打标签 ✅
  - `import_pipeline.py`：三条管线路径（native embedded / standard / resume_after_triage）MI/SM 创建后打 `AssetCustoms_ConfigProfile` 标签
  - `UnrealAssetOps` 新增 `set_metadata_tag()` + `remove_metadata_tag()` 方法
  - 测试：🤖 mock 验证调用参数 → 👁️ 导入后确认 tag 存在
- [x] Step 9：Content Browser 右键菜单查看/编辑 Profile ✅
  - `ui.py`：新增 "Config Profile ▸" 子菜单（View / Set Profile ▸ / Clear）
  - `actions.py`：新增 `on_view_config_profile()`、`on_set_config_profile(profile_name)`、`on_clear_config_profile()`
  - Profile 列表从 Config 目录动态扫描，支持多选资产批量操作
  - 测试：👁️ 菜单可见性 + View/Set/Clear 功能验证
- [x] Step 10：SP 发送配置驱动映射 ✅
  - `sp_bridge.py`：读取 SM tag → 加载 config → 将 `parameter_bindings` 注入 SP 数据包（顶层）
  - `sp_channel_map.py`：新增 `map_ue_to_sp_with_bindings()` 动态映射 + `_SUFFIX_TO_SP_CHANNEL` 字典
  - `sp_receive.py`：`resolve_channel()` 闭包按需选择动态/硬编码映射
  - 无 tag 时 fallback 到现有硬编码映射（向后兼容）
  - 测试：🤖 AssetCustoms 56 passed, SPsync 122 passed（+15 新增）

### Phase 5：Per-Material Profile + 多 TextureSet 支持

> 动机：一个 StaticMesh 可包含多个材质槽，不同材质可能对应不同 Profile（如 Body=Character, Weapon=Prop），
> Step 10 的"SM 顶层单 Profile"模型无法覆盖此场景。

**目标**：将 ConfigProfile 粒度从 SM 级提升到 MI 级，支持每个材质独立配置 + SP 侧多 TextureSet 分发。

- [x] Step 11：UE 侧 per-MI Profile 读取与数据包重构 ✅
  - `sp_bridge.py`：`_collect_material_info()` 改为逐材质读取 MI 上的 `AssetCustoms_ConfigProfile` tag
  - 新增 `material_slot_name` 字段：通过 `static_mesh.get_material_slot_names()` 获取材质槽名称
  - 每个 MI 独立加载对应 config → 提取 `parameter_bindings`
  - 数据包结构变更：`parameter_bindings` + `config_profile` + `material_slot_name` 注入 `materials[]` 每个元素
  - SM 顶层 `parameter_bindings` 保留作为 fallback（MI 无 tag 时继承 SM 的）
  - 测试：🤖 AssetCustoms 56 passed → 👁️ UE 验证
- [x] Step 12：SP 侧多 TextureSet 分发 ✅
  - `sp_receive.py`：`_on_project_ready()` 重构
    - 遍历 `textureset.all_texture_sets()` 构建 `{name: TextureSet}` 映射
    - 使用 `material_slot_name` 匹配 SP TextureSet（FBX 导出材质名 = UE 材质槽名）
    - 每个 TextureSet 使用其材质自带的 `parameter_bindings`（per-material 闭包）
    - 未匹配的材质输出 WARNING；单 TextureSet 时自动 fallback
  - 测试：🤖 SPsync 139 passed (44 sp_receive) → 🎨 SP 内多 TextureSet 验证
- [x] Step 13：材质槽名对应关系 + 匹配策略 ✅
  - **核心对应关系**：UE SM.material_slot_name ──FBX导出──→ SP TextureSet.name()
  - `match_material_to_textureset(material_name, ts_names, slot_name)`
  - 匹配优先级：① slot_name 精确 → ② slot_name 大小写不敏感 → ③ material_name 精确 → ④ 去 MI_ 前缀 → ⑤ 大小写不敏感
  - UE/SP 双侧输出 slot_name + material_name 日志，便于排查不匹配
  - 测试：🤖 14 项匹配策略单元测试 → 🔄 E2E 多材质发送验证
- [ ] Step 14：端到端验证 + 回归
  - 单材质 SM（向后兼容）：与 Step 10 行为一致
  - 多材质 SM 同 Profile：所有 MI 同一 Profile，结果一致
  - 多材质 SM 混合 Profile：Body=Character + Weapon=Prop，各自映射正确
  - 无 tag SM + 有/无 tag MI：各种 fallback 组合验证
  - 测试：🔄 4 种场景矩阵

### Phase 6：Grayscale Conversion Filter 通道拆分（Packed Texture 拆通道）

> 可行性验证：PoC 探测脚本 8/8 通过（`SPsync/tests/probe_filter_api.py`）
> 确认的 SP Python API 链：`resource.search()` → `insert_filter_effect()` → `SourceSubstance.set_parameters()`

**目标**：支持 Packed Texture（如 MRO）在 SP 中自动拆分为独立通道，使用 Grayscale Conversion Filter 按 RGBA 权重提取单通道。

**设计概要**：

1. **配置语法扩展**：`parameter_bindings` 支持 `.R/.G/.B/.A` 通道后缀
   ```jsonc
   // 之前（整包映射，MRO 只能映射到 Roughness）
   "parameter_bindings": { "MRO": "Packed_Texture" }
   // 之后（逐通道映射）
   "parameter_bindings": {
     "D": "BaseColor_Texture",
     "N": "Normal_Texture",
     "M": "Packed_Texture.R",    // Metallic ← R 通道
     "R": "Packed_Texture.G",    // Roughness ← G 通道
     "AO": "Packed_Texture.B"    // AO ← B 通道
   }
   ```

2. **SP 侧流程**：
   ```
   Fill Layer (Packed_Texture → 目标通道)
     └─ Filter Effect (Grayscale Conversion)
          grayscale_type = 1 (Channels Weights)
          Red = 1.0, Green = 0.0, Blue = 0.0, Alpha = 0.0  ← 按 .R/.G/.B/.A 设置
   ```

3. **已确认的 Filter 参数 Schema**：
   - `grayscale_type`: int — `{0: Desaturation, 1: Channels Weights, 2: Average, 3: Max, 4: Min}`
   - `Red/Green/Blue/Alpha`: float [0,1]
   - `channel_input`: int — `{0: Current Channel, 1: Custom Input}`
   - `invert`: int (bool)
   - `balance/contrast`: float [0,1]
   - Filter ResourceID: `starter_assets/grayscale_conversion/grayscale_conversion`

**实施步骤**：

- [x] Step 15a：通道后缀解析（`sp_channel_map.py`）
  - 新增 `parse_channel_suffix(binding_value)` → `(texture_param, channel_weights | None)`
  - 通道后缀映射：`.R` → `{Red:1,Green:0,Blue:0,Alpha:0}`，`.G/.B/.A` 同理
  - 无后缀时返回 `None`（走现有普通流程）
  - 测试：🤖 后缀解析 + 权重映射 + 边界用例
- [x] Step 15b：SP 侧 Filter Effect 插入（`sp_receive.py`）
  - `_on_project_ready()` 中识别带后缀的贴图
  - 创建 Fill Layer 后，插入 Grayscale Conversion Filter Effect
  - 设置 `grayscale_type=1` + 对应 RGBA 权重
  - 同一 Packed Texture 多通道复用资源（仅导入一次）
  - 测试：🤖 mock Filter 插入 + 参数验证 → 🎨 SP 内验证
- [x] Step 15c：UE 侧数据包扩展（`sp_bridge.py`）
  - `_collect_material_info()` 检测 `.R/.G/.B/.A` 后缀
  - 将拆分后的通道信息（`channel_suffix`）注入 `textures[]` 每个元素
  - 同一 Packed Texture 的多个引用共享同一导出文件路径
  - 测试：🤖 数据包结构验证 → 👁️ UE 侧验证
- [x] Step 15d：集成测试
  - MRO Packed Texture → SP 中自动创建 3 个 Fill Layer（M/R/AO 各一个）
  - 每个 Fill Layer 包含 Grayscale Conversion Filter + 正确的 RGBA 权重
  - 向后兼容：无后缀的 bindings 行为不变
  - 测试：🔄 E2E 验证

### 前置条件

| 条件 | 说明 |
|------|------|
| SP 启动参数 | 必须以 `--enable-remote-scripting` 启动 Substance Painter |
| SPsync 已安装 | SP 插件目录中需存在 SPsync 插件并启用 |
| vendor_libs 已部署 | AssetCustoms deploy.ps1 已执行 |

## M8 — 贴图尺寸控制（Texture Size Control）✅（已完成 2026-03-26）

> 可行性调研文档：[SPsync/doc/TEXTURE_SIZE_CONTROL.md]
> 设计原则：一切以配置文件中的 `max_resolution` 为准，全管线统一。

**目标**：在 `texture_definitions` 中为每张贴图定义最大分辨率（单个 int，POT），流经 UE 导入 → SP 项目创建 → SP 导出 全管线。

**配置格式**（最终实现）：
```jsonc
{
  "name": "Diffuse",
  "suffix": "D",
  // ... 现有字段 ...
  "max_resolution": 2048   // 单个 int（POT：256/512/1024/2048/4096），省略时不限制
}
```
- **类型**：`Optional[int]`（最初设计为 `{width, height}` 字典，M8 实施中统一简化为 `int`）
- 省略 `max_resolution` 时不限制分辨率（向后兼容）
- 值必须为 2 的幂（POT）

### 实施步骤

- [x] Phase 1：Config 格式扩展（schema.py + loader.py + Prop.jsonc + Character.jsonc）
- [x] Phase 2：UE 导入限制（import_textures_ue.py — `max_texture_size`）
- [x] Phase 3：SP 接收端设置分辨率（sp_receive.py — `default_texture_resolution` + `set_resolution`）
- [x] Phase 4：SP 导出尺寸控制（sp_channel_map.py — `sizeLog2`）
- [x] Phase 5：Config Editor UI（config_editor.py — max_resolution 控件）
- [x] Phase 6：测试与 E2E 验证

### 影响的文件

| 文件 | 变更说明 |
|------|----------|
| `core/config/schema.py` | `TextureProcessingDef.max_resolution: Optional[int]`；`TextureImportDefaults.max_resolution: Optional[int]` |
| `core/config/loader.py` | 解析 `max_resolution`（int） |
| `Prop.jsonc` / `Character.jsonc` | 每个 texture_definition 添加 `max_resolution`（int POT） |
| `sp_bridge.py` | 序列化 `max_resolution` + `texture_size` 到 SP 数据包 |
| `import_textures_ue.py` | 导入后设置 `max_texture_size` |
| `sp_receive.py` | 项目创建 `default_texture_resolution` + TextureSet `set_resolution`，Clamp [128, 4096] |
| `sp_channel_map.py` | 导出配置注入 `sizeLog2`（`_compute_export_size_log2()`） |
| `config_editor.py` | max_resolution 控件（int 输入） |

### 测试统计
- SPsync：191 passed
- AssetCustoms Core：103 passed, 20 skipped
- AssetCustoms 全量：56 passed（含 M7 UE 侧）
- Doctest：48 passed

## M9 — 分辨率权威分离（Resolution Authority Separation）✅（已完成 2026-03-26）

**目标**：解决 `blueprint_get_size_x/y()` 返回运行时分辨率（受 `max_texture_size`/LOD 影响）而非源文件分辨率的问题，确保 SP 端获得贴图的真实像素尺寸。

**核心改动**：
1. **`texture_size` 字段**：在 UE→SP 数据包中新增 `texture_size` 字段，值 = `max(tex_size_x, tex_size_y)`
2. **`update_texture_sizes_from_exports()`**：导出贴图到磁盘后，使用 PIL 读取实际导出文件的像素尺寸，覆盖 `texture_size` 值
3. **SP 端 Clamp [128, 4096]**：
   - `_compute_default_resolution()`：项目创建时的 `default_texture_resolution`，Clamp 到 [128, 4096]
   - `_compute_export_size_log2()`：导出时的 `sizeLog2`，Clamp 到 [128, 4096]（log2 ∈ [7, 12]）
4. **SP `project.create()` ValueError 修复**：textureSize=32 等过小值导致 SP 报错，Clamp 后消除

### 影响的文件

| 文件 | 变更说明 |
|------|----------|
| `sp_bridge.py` | 新增 `update_texture_sizes_from_exports()` 函数 + `texture_size` 序列化 |
| `sp_receive.py` | `_compute_default_resolution()` Clamp 逻辑 |
| `sp_channel_map.py` | `_compute_export_size_log2()` Clamp 逻辑 |

### 设计要点

- **权威来源**：贴图尺寸的权威来源从 `blueprint_get_size_x/y()`（可能被引擎限制）改为导出文件的实际像素尺寸
- **向后兼容**：无 `texture_size` 字段时 SP 端使用默认值 1024
- **Clamp 范围**：SP API 对 `default_texture_resolution` 和 `sizeLog2` 有范围要求，[128, 4096] 覆盖 SP 支持的全部 POT 值

## 风险与假设
- UE Python 环境与依赖管理差异大：Pillow、json5 建议随插件内置或提供等价注释剥离方案。
- 文件名/贴图规则存在多样性：必须优先“智能预填充”，回退到规则匹配与分诊 UI。

## 参考
- 架构说明见：[docs/architecture.md](./architecture.md)
- 详细需求规格（V1.1）：[docs/requirements_v1.1.md](./requirements_v1.1.md)
- 决策记录示例：[docs/decisions/ADR-0001.md](./decisions/ADR-0001.md)

## 开发计划（v1.1 拆分）

M1 架构拆分与底座
- 建立 `core` 与 `unreal_integration` 目录与最小可用 API。
- 定义核心 API：`core.textures.layer_merge.merge_layers`、`core.config.loader.load_config`。
- 适配层最小管道：从 Texture 读取像素 -> 调用核心 -> 回写结果（占位实现）。
- 基础单元测试（纯 Python）。

M2 贴图图层合并（核心能力）
- 支持基础混合模式：Normal/Multiply/Screen/Overlay/Add/Subtract。
- 支持图层不透明度、尺寸对齐与背景色。
- 性能基线与回退路径（无 numpy 时可用但较慢）。

M3 配置解析（核心能力）
- 定义配置 Schema 与默认值。
- JSON 为默认实现，YAML 作为可选扩展（后续）。
- 支持从路径、字符串、字典载入；校验与错误报告。

M4 Unreal 集成
- Texture2D/RenderTarget 像素桥接。
- 项目设置映射为核心配置。
- 端到端示例命令与日志。

验收标准
- 纯 Python 核心可在无 Unreal 环境下运行与测试。
- Unreal 中可调用适配层完成简单的图层合并管道。
- 文档包含模块边界、API 约定与示例。

## E2E 验证（2026-03-22）
- 外部贴图 E2E：✅ 通过
- 原生嵌入贴图 E2E：✅ 通过（FR2.5 管线）
- 外部贴图回归：✅ 通过
- SM→MI 绑定验证：✅ slot[0] = MI, parent = MM_Prop_PBR, 贴图参数全部绑定
- FR4 分诊 UI 视觉验证：✅ 通过（UE 编辑器内弹出 + 交互确认）
- 总计：90 tests（70 passed, 20 skipped）
- 总计：82 unit tests + 3 E2E tests

## 最近测试（2025-11-11）
- 环境：Windows / Python 3.11.8 / pytest 8.4.2
- 结果：6 项单测全部通过（core.config 与 core.textures.layer_merge）
