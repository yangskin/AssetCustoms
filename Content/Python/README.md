# Content/Python 说明

此目录包含 Unreal 插件的 Python 入口与后续工具脚本。

- 入口脚本：`init_unreal.py`
- 运行方式：在 UE Editor 打开项目并启用插件时，Unreal 会加载本目录下的 `init_unreal.py`。
- 建议：将业务回调放入独立 `Actions` 类，`AssetCustomsUI` 仅负责菜单/工具栏注册与回调转发。

## 最小用法（思路）

- `init_unreal.py` 暴露 `CONFIG`，并在其中定义要注册的菜单/工具栏项；开启 `auto_register` 可在加载时自动注册。
- 推荐将 UI 单例挂到 `unreal` 模块上，避免多模块名/热重载造成引用丢失（当前入口已内置处理）。

## 相关文档
- 架构说明：`../../docs/architecture.md`
- 需求规格（V1.1）：`../../docs/requirements_v1.1.md`
- 路线图：`../../docs/roadmap.md`
- 编码规范：`../../standards/coding-style.md`
- Review 检查单：`../../standards/review-checklist.md`
- 提交规范：`../../standards/commit-convention.md`
