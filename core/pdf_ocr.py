# -*- coding: utf-8 -*-
"""
core/pdf_ocr.py
OCR trang PDF dạng ảnh (không có text layout) bằng Tesseract.
Mặc định dùng tiếng Việt (lang=vie).
"""

from __future__ import annotations

import os
from pathlib import Path

import fitz  # PyMuPDF

from config import TESSERACT_CMD, TESSERACT_LANG, TESSERACT_OCR_ZOOM


def _configure_tesseract() -> None:
    import pytesseract

    cmd = (TESSERACT_CMD or "").strip()
    if not cmd:
        # Đường dẫn cài đặt mặc định trên Windows (UB-Mannheim)
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in candidates:
            if Path(path).is_file():
                cmd = path
                break
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def ocr_pdf_page(
    pdf_path: str | Path,
    page_number: int,
    *,
    lang: str | None = None,
    zoom: float | None = None,
) -> str:
    """
    Raster hóa 1 trang PDF rồi OCR bằng Tesseract.
    page_number: chỉ số trang bắt đầu từ 1.
    Trả về chuỗi text (có thể rỗng nếu lỗi / không đọc được).
    """
    path = Path(pdf_path)
    if not path.is_file() or page_number < 1:
        return ""

    from PIL import Image
    import pytesseract

    _configure_tesseract()
    use_lang = (lang or TESSERACT_LANG or "vie").strip() or "vie"
    use_zoom = float(zoom if zoom is not None else TESSERACT_OCR_ZOOM)

    doc = fitz.open(path)
    try:
        if page_number > doc.page_count:
            return ""
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(use_zoom, use_zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        try:
            text = pytesseract.image_to_string(img, lang=use_lang) or ""
        except pytesseract.TesseractError:
            # Fallback nếu thiếu gói vie
            if use_lang != "eng":
                text = pytesseract.image_to_string(img, lang="eng") or ""
            else:
                raise
        return text.strip()
    finally:
        doc.close()


def page_has_text_layout(full_text: str, words: list | None = None) -> bool:
    """True nếu trang đã có text/layout đủ dùng (không cần OCR)."""
    if (full_text or "").strip():
        return True
    if words and len(words) > 0:
        return True
    return False
