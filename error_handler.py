# -*- coding: utf-8 -*-
"""
error_handler.py
Logging helper dùng chung cho toàn bộ ứng dụng.
"""

import logging
import os
from datetime import datetime

# --------------------------------------------------------------------------- #
# Cấu hình logging ghi ra file + console
# --------------------------------------------------------------------------- #
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

_log_file = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("print-server")


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #

def log_error(context: str, exc: Exception, extra: dict = None):
    msg = f"[ERROR] {context}: {exc}"
    if extra:
        msg += f" | extra={extra}"
    logger.error(msg)


def log_success(message: str):
    logger.info(f"[OK] {message}")


def log_warning(message: str):
    logger.warning(f"[WARN] {message}")


def log_info(message: str):
    logger.info(f"[INFO] {message}")
