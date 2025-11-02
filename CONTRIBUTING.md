# 贡献指南

感谢关注本项目！以下流程帮助你高效参与协作。

## 分支策略（建议）
- `main`：稳定分支，保持可用；
- `dev`：日常集成分支；
- `feature/*`：功能分支，例如 `feature/asset-scan`。

## 开发流程
1. 从最新 `dev` 切出 `feature/*` 分支；
2. 按规范提交（见 `standards/commit-convention.md`）；
3. 发起 PR 合入 `dev`，过 Review 后再合入 `main`；
4. 重要变更补充文档与 ADR（如适用）。

## 提交信息
- 遵循 Conventional Commits；
- 提交粒度小而明确；
- PR 标题与描述清晰说明动机、方案与验证方式。

## 代码风格与质量
- 遵循 `standards/coding-style.md`；
- 按 `standards/review-checklist.md` 自查后再提交 PR；
- 尽量增加日志与错误处理，避免影响 UE 稳定性。

## 在 Unreal 环境中开发的小贴士
- 避免阻塞主线程的耗时操作；必要时分批或异步处理；
- 第三方依赖要谨慎评估安装可行性与兼容性；
- 使用 `unreal.log*` 输出清晰、可检索的日志。

## 报告问题 / 建议
- 提交 Issue 时请附：版本信息、复现步骤、期望结果、实际结果、日志片段。

## 行为准则
- 友善、尊重、包容；以事实与数据为依据开展讨论。
