"""模型公共工具。"""

from __future__ import annotations

from uuid import uuid4


def new_id(prefix: str = "") -> str:
    """生成短唯一标识；可选前缀便于阅读（如 AC、WP、RT）。"""
    return f"{prefix}{uuid4().hex[:12]}" if prefix else uuid4().hex[:12]
