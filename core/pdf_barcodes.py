# -*- coding: utf-8 -*-
"""Nhận dạng barcode trên từng trang PDF (PyMuPDF + zxing-cpp)."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
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


def _pairs_from_page_render(page: fitz.Page, zoom: float) -> list[tuple[str, str]]:
    """Raster hóa trang (vector hoặc ảnh) rồi decode."""
    from PIL import Image

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return _pairs_from_pil_image(img, max_codes=None)


def _pairs_from_embedded_images(doc: fitz.Document, page: fitz.Page) -> list[tuple[str, str]]:
    """
    Quét từng ảnh XObject nhúng trong trang (PDF dạng scan / toàn ảnh).
    Dùng byte gốc của ảnh, tránh mất chi tiết do render lại.
    """
    from PIL import Image

    seen_text: set[str] = set()
    out: list[tuple[str, str]] = []
    xrefs_seen: set[int] = set()
    for info in page.get_images(full=True):
        xref = int(info[0])
        if xref in xrefs_seen:
            continue
        xrefs_seen.add(xref)
        try:
            bd = doc.extract_image(xref)
        except Exception:
            continue
        data = bd.get("image")
        if not data:
            continue
        try:
            im = Image.open(BytesIO(data))
            im = im.convert("RGB")
        except Exception:
            continue
        for text, sym in _pairs_from_pil_image(im, max_codes=None):
            if text in seen_text:
                continue
            seen_text.add(text)
            out.append((text, sym))
    return out


def _barcodes_for_page(
    doc: fitz.Document,
    page: fitz.Page,
    *,
    zoom: float = 2.0,
) -> list[tuple[str, str]]:
    """
    Thứ tự: render (zoom mặc định) → render zoom cao hơn → ảnh nhúng trong trang.
    """
    pairs = _pairs_from_page_render(page, zoom)
    if pairs:
        return pairs
    hi_zoom = max(zoom * 1.75, 3.5)
    if hi_zoom > zoom + 0.01:
        pairs = _pairs_from_page_render(page, hi_zoom)
        if pairs:
            return pairs
    return _pairs_from_embedded_images(doc, page)


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

    doc = fitz.open(path)
    try:
        if page_number > doc.page_count:
            return []
        page = doc[page_number - 1]
        pairs = _barcodes_for_page(doc, page, zoom=zoom)
        if max_codes is not None:
            pairs = pairs[:max_codes]
        return pairs
    finally:
        doc.close()


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

    out: dict[int, list[tuple[str, str]]] = {}
    doc = fitz.open(path)
    try:
        for i in range(doc.page_count):
            page = doc[i]
            pairs = _barcodes_for_page(doc, page, zoom=zoom)
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
