# -*- coding: utf-8 -*-
"""Nhận dạng barcode trên từng trang PDF (PyMuPDF + zxing-cpp)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import fitz  # PyMuPDF


def _format_to_str(fmt) -> str:
    if fmt is None:
        return ""
    name = getattr(fmt, "name", None)
    if name:
        return str(name)
    return str(fmt)


def _pairs_from_pil_image(
    img,
    *,
    max_codes: int | None = 3,
) -> list[tuple[str, str]]:
    import zxingcpp

    decoded = zxingcpp.read_barcodes(img)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for b in decoded:
        text = (getattr(b, "text", None) or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append((text, _format_to_str(getattr(b, "format", None))))
        if max_codes is not None and len(out) >= max_codes:
            break
    return out


def read_barcodes_on_pdf_page(
    pdf_path: str | Path,
    page_number: int,
    *,
    zoom: float = 2.0,
    max_codes: int = 3,
) -> list[tuple[str, str]]:
    """
    page_number: chỉ số trang bắt đầu từ 1 (giống scan_pdf / FileOrder.page_number).
    Trả về tối đa max_codes mã, bỏ qua trùng nội dung (giữ thứ tự zxing trả về).
    Mỗi phần tử: (text, symbology).
    """
    path = Path(pdf_path)
    if not path.is_file() or page_number < 1:
        return []

    from PIL import Image

    doc = fitz.open(path)
    try:
        if page_number > doc.page_count:
            return []
        page = doc[page_number - 1]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()

    return _pairs_from_pil_image(img, max_codes=max_codes)


def scan_pdf_all_pages_barcodes(
    pdf_path: str | Path,
    *,
    zoom: float = 2.0,
) -> dict[int, list[tuple[str, str]]]:
    """
    Mở PDF một lần, quét barcode từng trang (không giới hạn số mã / trang).
    Chỉ có key cho trang có ít nhất một mã: page_1based -> [(text, symbology), ...].
    """
    path = Path(pdf_path)
    if not path.is_file():
        return {}

    from PIL import Image

    out: dict[int, list[tuple[str, str]]] = {}
    doc = fitz.open(path)
    try:
        for i in range(doc.page_count):
            page = doc[i]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pairs = _pairs_from_pil_image(img, max_codes=None)
            if pairs:
                out[i + 1] = pairs
    finally:
        doc.close()
    return out


def barcode_fields_from_pairs(pairs: Sequence[tuple[str, str]]) -> dict[str, str | None]:
    """Khớp các cột OrderPrint: barcode_1..3, type_1..3."""
    fields: dict[str, str | None] = {}
    for i in range(1, 4):
        fields[f"barcode_{i}"] = None
        fields[f"type_{i}"] = None
    for idx, (text, fmt) in enumerate(pairs[:3], start=1):
        fields[f"barcode_{idx}"] = (text[:255] if text else None)
        fields[f"type_{idx}"] = (fmt[:50] if fmt else None)
    return fields
