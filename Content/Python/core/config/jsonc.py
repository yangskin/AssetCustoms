"""
Minimal JSONC reader:
- Prefer json5 if available (supports comments, trailing commas, etc.).
- Fallback: strip // and /* */ comments and remove trailing commas, then json.loads.

Note: This is a lightweight parser for configuration use cases. It won't cover
all edge cases of JSON5; for complex configs, install `json5`.
"""
from __future__ import annotations

import re
import json
from typing import Any


def _strip_jsonc(src: str) -> str:
    # Remove /* block */ comments (non-greedy, dotall)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    # Remove // line comments (ignore within strings – naive approach)
    # A simple heuristic: remove // to end of line when not inside quotes is hard;
    # for most configs, removing //.* works well enough when comments are standalone.
    src = re.sub(r"(^|[^:\\])//.*$", r"\1", src, flags=re.M)
    # Remove trailing commas before } or ]
    src = re.sub(r",\s*([}\]])", r"\1", src)
    return src


def loads_jsonc(text: str) -> Any:
    try:
        import json5  # type: ignore

        return json5.loads(text)
    except Exception:
        cleaned = _strip_jsonc(text)
        return json.loads(cleaned)


def load_jsonc_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return loads_jsonc(content)
