# -*- coding: utf-8 -*-
"""
config.py — Cấu hình ứng dụng, load từ .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ── Database ──────────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", 3306))
DB_USER     = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME", "print_server")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# ── Label PDF — barcode / QR enlargement ─────────────────────
BARCODE_ENLARGE_ENABLED    = os.getenv("BARCODE_ENLARGE_ENABLED", "true").lower() in ("1", "true", "yes")
BARCODE_MIN_WIDTH_PT       = float(os.getenv("BARCODE_MIN_WIDTH_PT", "150"))
BARCODE_TARGET_WIDTH_RATIO = float(os.getenv("BARCODE_TARGET_WIDTH_RATIO", "0.50"))
BARCODE_MIN_HEIGHT_RATIO   = float(os.getenv("BARCODE_MIN_HEIGHT_RATIO", "0.055"))

QR_ENLARGE_ENABLED         = os.getenv("QR_ENLARGE_ENABLED", "true").lower() in ("1", "true", "yes")
QR_MIN_SIZE_PT             = float(os.getenv("QR_MIN_SIZE_PT", "85"))
QR_TARGET_SIZE_RATIO       = float(os.getenv("QR_TARGET_SIZE_RATIO", "0.20"))
