"""
简易测试启动器：
- 安装依赖：`python -m pip install -r requirements-dev.txt`
- 运行：`python run_tests.py`
"""
import sys
import os

try:
    import pytest  # type: ignore
except Exception as e:
    print("[ERROR] pytest 未安装，请先执行: python -m pip install -r requirements-dev.txt", file=sys.stderr)
    sys.exit(2)

ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(ROOT, "Content", "Python", "core", "tests")

if __name__ == "__main__":
    # 要求使用虚拟环境运行（提示而不强制退出）
    in_venv = (hasattr(sys, "real_prefix") or getattr(sys, "base_prefix", sys.prefix) != sys.prefix)
    if not in_venv:
        print("[WARN] 检测到当前未在虚拟环境中运行，建议先执行: python -m venv .venv && .\\.venv\\Scripts\\Activate.ps1", file=sys.stderr)
    sys.exit(pytest.main([TESTS]))
