# 路线图 / 里程碑（V1.1）

版本: V1.1（Config v1.1）  |  状态: 需求已确认  |  负责人: （您的名字/TA团队）  |  最后更新: 2025-11-01

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

## M2 — V1.1 功能落地（当前阶段）
- [ ] FR1：TA 配置系统（JSONC、Profile 扫描/加载、Schema v1.1）
	- 进度：
		- [x] JSONC 解析能力完成（优先 json5，回退注释剥离+尾逗号处理）。
		- [x] `Content/Config/AssetCustoms/Prop.jsonc` 默认 Profile 提供。
		- [x] `core.config.loader.load_config()` 输出数据类 `PluginConfig`，含默认值。
		- [ ] Unreal 侧 Profile 扫描与选择（待接入 UI）。
- [ ] FR2：内容浏览器下拉按钮（动态填充 Profile，带上下文的文件选择）
	- 进度：
		- [x] 在 Content Browser 工具栏注册入口按钮“Import FBX…”。
		- [x] 使用 tkinter 文件对话框，仅允许选择 .fbx，支持多选；记录当前 Content Browser 路径。
		- [ ] 下拉动态 Profile 列表（待 FR1 Unreal 侧扫描完成后串联）。
- [ ] FR3：自动化检查链（模型数量、主材质、贴图映射 智能预填充+规则匹配）
- [ ] FR4：分诊 UI（失败时弹出：原因、预填、歧义处理、命名确认、执行按钮）
- [ ] FR5：标准化引擎（Pillow 贴图处理/打包、重命名/移动、MIC 创建/链接、导入设置、清理）
	- 进度：
		- [x] 贴图图层合并核心能力（`core.textures.layer_merge.merge_layers`）实现并通过单测（numpy 快路径 + Pillow 回退）。

## M3 — 质量与体验
- [ ] 性能预算：典型资产“静默成功”全流程 ≤ 5s（NFR1）
- [ ] 健壮性：失败停止在“隔离区”，编辑器不崩溃（NFR3）
- [ ] 未找到配置时 UI 提示并禁用入口（NFR4）

## M4 — 集成与扩展
- [ ] 批处理/CI 集成（可选）
- [ ] 配置 Schema 扩展与向后兼容策略

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
