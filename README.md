# AssetCustoms（Python）文档索引

本插件的项目文档位于仓库根目录；Python 工具代码位于 `Content/Python/`，入口脚本为 `Content/Python/init_unreal.py`。

## 文档导航
- 路线图 / 里程碑：[`docs/roadmap.md`](docs/roadmap.md)
- 系统架构 / 模块边界 / 数据流：[`docs/architecture.md`](docs/architecture.md)
- 需求规格（V1.1）：[`docs/requirements_v1.1.md`](docs/requirements_v1.1.md)
- 决策记录（ADR）：[`docs/decisions/ADR-0001.md`](docs/decisions/ADR-0001.md)
- 编码规范：[`standards/coding-style.md`](standards/coding-style.md)
- Code Review 检查单：[`standards/review-checklist.md`](standards/review-checklist.md)
- 提交规范：[`standards/commit-convention.md`](standards/commit-convention.md)
- 贡献指南：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 安全策略：[`SECURITY.md`](SECURITY.md)

## 快速了解
- 目标：提供围绕 UE 的资产处理与自动化能力（Python 脚本）。
- 范围：轻依赖、可扩展、以文档与规范先行，功能增量演进。

## 开发提示（初稿）
- 在 UE Editor 中加载插件时会调用 `init_unreal.py`；确保日志可见性良好。
- 变更公共行为时请更新文档，并考虑补充 ADR。
- V1.1 依赖：插件需内置 Pillow（PIL）与 JSONC 解析能力（json5 或注释剥离器）。

如需贡献或提问，请先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
