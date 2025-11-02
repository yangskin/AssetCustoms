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
    sys.exit(pytest.main([TESTS]))
