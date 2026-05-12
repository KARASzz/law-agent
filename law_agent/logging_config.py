"""应用日志初始化。"""

from __future__ import annotations

import sys
from typing import Any

from loguru import logger


def configure_logging(config: Any) -> None:
    """配置 loguru，保持控制台输出简洁。"""
    logger.remove()
    level = "DEBUG" if getattr(getattr(config, "server", None), "debug", False) else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        enqueue=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
