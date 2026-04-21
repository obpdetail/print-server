# -*- coding: utf-8 -*-
"""
core/printing.py
Xử lý in ấn PDF: merge label, gửi lệnh in, quản lý trạng thái in.
"""

import os

import win32api

# from error_handler import log_error, log_success, log_warning


def print_pdf_printer(filepath, printer_name=None):
    printer_name = "Y486 Label"
    try:
        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File không tồn tại: {abs_path}")

        win32api.ShellExecute(
            0,
            "printto",
            abs_path,
            f'"{printer_name}"',
            ".",
            0
        )

        print(f"✅ Đã gửi lệnh in: {abs_path} -> {printer_name or 'Default Printer'}")
        return True

    except Exception as e:
        print(f"❌ Lỗi khi gửi lệnh in: {e}")
        return False