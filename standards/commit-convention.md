# 提交规范（Conventional Commits）

采用 Conventional Commits 约定统一提交历史。

## 格式
```
<type>(<scope>): <subject>

<body>

<footer>
```
- `type`：feat | fix | docs | style | refactor | perf | test | build | ci | chore | revert
- `scope`：可选，建议使用模块或目录名，例如：unreal、plugin、docs、ci
- `subject`：简述变更，使用祈使语气，尽量不超过 72 字符

### BREAKING CHANGE
- 若为破坏性变更，在正文或页脚加入：
```
BREAKING CHANGE: 描述影响与迁移方式
```

## 示例
- `feat(unreal): 新增资产扫描命令`
- `fix(plugin): 修复 init_unreal.py 日志初始化异常`
- `docs(adr): 记录 ADR-0001 文档与流程规范`
- `chore: 调整项目文档结构`

## 自动化提交约束

- 禁止任何脚本、CI、Bot 在未获得“显式授权提示词”的情况下执行 `git commit` 或 `git push` 到远端仓库。
- 显式授权提示词示例：
	- “请提交到 GitHub”
	- “执行 Git 提交并推送”
- 允许例外：经人工触发并审核通过的发布流水线可创建 tag 或 release。
- 实施建议：
	- 默认 dry-run：先输出将要提交的变更清单与命令，要求二次确认后再执行。
	- 工具/脚本需显式参数或交互确认（例如 `--allow-commit`）才可执行提交/推送。

## 最佳实践
- 每次提交保持单一意图，方便回溯与回滚。
- 与 PR 标题保持一致风格；PR 描述补充动机与验证方式。
