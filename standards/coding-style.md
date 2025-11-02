# 编码规范（Google Python Style + Unreal 实践）

本规范采用 Google Python Style Guide 作为主要来源；未覆盖之处遵循 PEP 8/PEP 257。结合 Unreal 环境补充日志与异常实践。

## 关键约定
- 行宽：80 字符（必要时可放宽至 100，但需保持可读性）。
- 缩进：4 空格；禁止 Tab。
- 编码：UTF-8；换行按仓库默认。
- 导入顺序：标准库 -> 第三方 -> 项目内；每组之间空行；禁止通配符导入。
- 导入风格：优先绝对导入；避免相对导入（除非确有必要）。

## 命名
- 模块/包：lower_with_underscores，例如 `asset_tools.py`。
- 类：CapWords（PascalCase），例如 `ProfileLoader`。
- 函数/变量：lower_with_underscores，例如 `build_isolation_path()`。
- 常量：UPPER_SNAKE_CASE，例如 `DEFAULT_PROFILE_DIR`。
- 非公开成员：前导单下划线，例如 `_resolve_profile_path()`。

## Docstring（Google 风格）
- 使用三引号；首行简述，空行后给出详细说明。
- 参数、返回值、异常采用 Google 风格段落。
- 公共 API 必须有 Docstring；内部函数在复杂逻辑时也应补充。

示例：
```python
import unreal
from typing import Iterable

def build_isolation_path(current_path: str, base_name: str) -> str:
        """Compute unique isolation path under the given content path.

        Args:
            current_path: UE content path selected in Content Browser.
            base_name: FBX base file name without extension.

        Returns:
            The isolation path like "/Game/Props/Crates/_temp_MyCrate".

        Raises:
            ValueError: If current_path is empty or invalid.
        """
        if not current_path:
                raise ValueError("current_path is empty")
        return f"{current_path.rstrip('/')}/_temp_{base_name}"


def validate_assets(paths: Iterable[str]) -> int:
        """Validate asset paths and log issues to Unreal.

        Args:
            paths: An iterable of asset paths.

        Returns:
            Number of issues found.
        """
        issues = 0
        for p in paths:
                try:
                        if not p or not isinstance(p, str):
                                issues += 1
                                unreal.log_warning(f"Invalid asset path: {p}")
                except Exception as exc:  # Avoid bare except
                        unreal.log_error(f"validate_assets error: {exc}")
        return issues
```

## 类型标注（Typing）
- 推荐为公共函数/方法添加类型标注；复杂结构可使用 `TypedDict`/`Protocol`。
- 返回值显式声明；`None` 返回使用 `-> None`。
- 运行时不强制类型检查，但建议在本地/CI 用 `mypy`（若环境允许）。

## 字符串与格式化
- 优先使用 f-string；避免 `+` 拼接长字符串。
- 跨行字符串可使用括号隐式拼接或 `textwrap.dedent`。

## 注释
- 解释“为什么”而非“做了什么”。
- TODO 采用格式：`TODO(username): 描述`。

## 异常与错误处理（结合 Unreal）
- 抛出具体异常类型；入口或边界位置统一捕获并记录日志。
- 避免裸 `except`；使用 `except Exception as exc:` 并写入上下文。
- UE 日志 API：`unreal.log()`、`unreal.log_warning()`、`unreal.log_error()`；日志包含模块、资产、操作结果。
- 遵循“静默成功，响亮失败”：失败时停止破坏性操作，并输出明确可行动的日志。

## 依赖与环境
- 轻依赖优先；V1.1 需内置 Pillow 与 JSONC 解析（json5 或注释剥离）。
- 第三方库必须集中初始化与可用性检测，无法满足时提供降级或清晰提示。

## 提交与评审
- 提交信息遵循 Conventional Commits（见 `standards/commit-convention.md`）。
- 建议在 PR 描述中标注涉及 FR/NFR 项，说明验证方式与性能影响。

## 样式检查（可选建议）
- 若仓库允许：`ruff` 做静态检查，`black` 做格式化（注意与 80 列规则协商）。
- 在 UE 环境不便时，可本地预检查；以可读性为先。
