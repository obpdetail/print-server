# -*- coding: utf-8 -*-
"""
core/printing.py
Gửi PDF tới máy in Windows.
"""

import os
import sys
from pathlib import Path

import win32api

_CORE_DIR = Path(__file__).resolve().parent
_ROOT = _CORE_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from pdf_enlarge import enlarge_barcode_in_pdf


def print_pdf_printer(filepath, printer_name=None):
    printer_name = printer_name or "Y486 Label"
    try:
        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File không tồn tại: {abs_path}")

        enlarge_barcode_in_pdf(abs_path)

        win32api.ShellExecute(
            0,
            "printto",
            abs_path,
            f'"{printer_name}"',
            ".",
            0,
        )

        print(f"✅ Đã gửi lệnh in: {abs_path} -> {printer_name}")
        return True

    except Exception as e:
        print(f"❌ Lỗi khi gửi lệnh in: {e}")
        return False
