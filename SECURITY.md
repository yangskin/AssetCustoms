# 安全策略

本文件说明如何报告安全问题以及项目的基本安全实践。

## 报告安全问题
- 请通过电子邮件联系：security@example.com（请替换为实际安全联络邮箱）。
- 或在私密渠道提供最小复现与影响范围，我们将尽快响应。

## 支持范围
- 仅对本目录下的 Python 脚本与文档提供安全支持。
- 不直接涵盖 Unreal Engine 核心与第三方插件漏洞。

## 最佳实践
- 不要将密钥、令牌、内部地址等敏感信息写入仓库或日志。
- 如需配置凭据，请使用环境变量或本地受控文件，并在 `.gitignore` 中忽略。
- 外部输入与路径需做校验与最小权限处理，避免任意文件访问。

## 漏洞披露
- 我们倾向于负责任披露流程：先私下报告，修复后再公开细节。

## 参考
- 提交规范：[`standards/commit-convention.md`](standards/commit-convention.md)
- Review 检查单：[`standards/review-checklist.md`](standards/review-checklist.md)
