# 路线图 / 里程碑（V1.1）

版本: V1.1（Config v1.1）  |  状态: M4 已完成  |  负责人: （您的名字/TA团队）  |  最后更新: 2026-03-23

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

## M5 — Config v2.0 三段式管线模型（设计已确认 2026-03-23）

> 设计文档：[ADR-0002](./decisions/ADR-0002-config-v2-pipeline-model.md)（状态：已确认）

**目标**：将扁平的 v1.1 配置重构为 Input → Processing → Output 三段式嵌套结构，消除"处理定义"与"交付设置"混杂的问题：
- `input`：贴图识别规则（`texture_rules`），Mesh/Material 仅注释占位。
- `processing`：命名模板、冲突策略、贴图处理定义（Pillow 通道编排 + format/bit_depth/srgb/mips）。
- `output`：目标路径、子目录、导入设置默认值、逐贴图 import override（集中表格）。

**关键决策**（Q1-Q6 已确认）：
- `format`/`bit_depth`/`srgb`/`mips` 保留在 `processing`
- `conflict_policy` 保留在 `processing`
- `parameter_bindings` 以 `suffix` 为 key
- `texture_merge`/`allowed_modes` 直接删除
- `input.mesh`/`input.material` 暂留注释占位
- `texture_import_overrides` 采用 Output Tab 集中表格（方案 A）

**实施计划**（5 步）：
- [ ] Step 1：Schema + Loader 重写（`schema.py` → 3 dataclass 嵌套，`loader.py` 适配）
- [ ] Step 2：JSONC 模板迁移（`Prop.jsonc`、`Character.jsonc` → v2.0 结构）
- [ ] Step 3：管线代码适配（`naming.py`、`import_pipeline.py`、`standardize.py` 等字段路径更新）
- [ ] Step 4：Config Editor UI 重构（3 Tab：Input / Processing / Output）
- [ ] Step 5：测试 & 回归（全量测试通过 + E2E 验证）

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
