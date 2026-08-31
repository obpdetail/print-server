# -*- coding: utf-8 -*-
"""
core/pdf_enlarge.py
Phóng to barcode / QR code trên nhãn vận chuyển nếu Shopee trả về quá nhỏ.
"""

import os
import sys
from pathlib import Path

import fitz

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import (
    BARCODE_ENLARGE_ENABLED,
    BARCODE_MIN_HEIGHT_RATIO,
    BARCODE_MIN_WIDTH_PT,
    BARCODE_TARGET_WIDTH_RATIO,
    QR_ENLARGE_ENABLED,
    QR_MIN_SIZE_PT,
    QR_TARGET_SIZE_RATIO,
)
from error_handler import log_success


def _find_image_barcode(page: fitz.Page) -> tuple[fitz.Rect, int] | None:
    page_w = page.rect.width
    candidates: list[tuple[float, fitz.Rect, int]] = []

    for img in page.get_images(full=True):
        xref = img[0]
        for rect in page.get_image_rects(xref):
            if rect.height <= 0 or rect.y0 > page.rect.height * 0.15:
                continue

            aspect = rect.width / rect.height
            x_center = (rect.x0 + rect.x1) / 2 / page_w

            if x_center < 0.28:
                continue
            if x_center < 0.42 and aspect < 4.5:
                continue
            if aspect < 2.5:
                continue

            score = aspect * (0.4 + x_center)
            candidates.append((score, rect, xref))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], -item[1].width))
    _, rect, xref = candidates[0]
    return rect, xref


def _find_vector_barcode_rect(page: fitz.Page) -> fitz.Rect | None:
    page_w, page_h = page.rect.width, page.rect.height
    bar_rects: list[fitz.Rect] = []

    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if not rect or rect.y0 > page_h * 0.12:
            continue

        x_center = (rect.x0 + rect.x1) / 2 / page_w
        n_items = len(drawing.get("items", []))

        if x_center < 0.30:
            continue
        if rect.width < 80 or not (10 < rect.height < 55):
            continue
        if n_items < 8:
            continue

        bar_rects.append(rect)

    if not bar_rects:
        return None

    return fitz.Rect(
        min(r.x0 for r in bar_rects),
        min(r.y0 for r in bar_rects),
        max(r.x1 for r in bar_rects),
        max(r.y1 for r in bar_rects),
    )


def _find_qr_image(page: fitz.Page, doc: fitz.Document) -> tuple[fitz.Rect, int] | None:
    page_w, page_h = page.rect.width, page.rect.height
    candidates: list[tuple[float, fitz.Rect, int]] = []

    for img in page.get_images(full=True):
        xref = img[0]
        info = doc.extract_image(xref)
        nw, nh = info["width"], info["height"]
        native_aspect = nw / nh if nh else 0

        for rect in page.get_image_rects(xref):
            if rect.height <= 0 or rect.y0 < page_h * 0.18:
                continue

            aspect = rect.width / rect.height
            is_square = (0.75 <= aspect <= 1.35) or (0.75 <= native_aspect <= 1.35)
            if not is_square:
                continue

            x_center = (rect.x0 + rect.x1) / 2 / page_w
            if x_center < 0.45:
                continue

            size = max(rect.width, rect.height)
            candidates.append((size, rect, xref))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], -item[1].x0))
    _, rect, xref = candidates[0]
    return rect, xref


def _replace_enlarged_image(
    page: fitz.Page,
    rect: fitz.Rect,
    *,
    image_bytes: bytes | None = None,
    pixmap: fitz.Pixmap | None = None,
    new_width: float,
    new_height: float,
) -> None:
    new_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + new_width, rect.y0 + new_height)
    pad = 3
    wipe = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
    page.add_redact_annot(wipe, fill=(1, 1, 1))
    page.apply_redactions()
    if pixmap is not None:
        page.insert_image(new_rect, pixmap=pixmap)
    else:
        page.insert_image(new_rect, stream=image_bytes)


def _enlarge_barcode_region(page: fitz.Page, rect: fitz.Rect, target_width: float, target_height: float) -> bool:
    margin = 8
    max_width = page.rect.width - rect.x0 - margin
    max_height = page.rect.height * 0.12 - rect.y0

    scale_w = target_width / rect.width if rect.width < target_width else 1.0
    scale_h = target_height / rect.height if rect.height < target_height else 1.0
    scale = max(scale_w, scale_h)

    new_w = rect.width * scale
    new_h = rect.height * scale
    if new_w > max_width:
        scale = max_width / rect.width
        new_w = max_width
        new_h = rect.height * scale
    if new_h > max_height:
        scale = min(scale, max_height / rect.height)
        new_h = rect.height * scale
        new_w = rect.width * scale

    if scale <= 1.02:
        return False

    render_scale = 4
    pix = page.get_pixmap(matrix=fitz.Matrix(render_scale, render_scale), clip=rect, alpha=False)
    _replace_enlarged_image(page, rect, pixmap=pix, new_width=new_w, new_height=new_h)
    return True


def _enlarge_qr_on_page(page: fitz.Page, doc: fitz.Document, target_size: float) -> bool:
    found = _find_qr_image(page, doc)
    if not found:
        return False

    rect, xref = found
    current = max(rect.width, rect.height)
    if current >= target_size * 0.95:
        return False

    margin = 8
    max_size = min(
        page.rect.width - rect.x0 - margin,
        page.rect.height - rect.y0 - margin,
        target_size,
    )
    if max_size <= current * 1.02:
        return False

    img_bytes = doc.extract_image(xref)["image"]
    _replace_enlarged_image(
        page, rect, image_bytes=img_bytes, new_width=max_size, new_height=max_size,
    )
    return True


def enlarge_barcode_in_pdf(
    pdf_path: str,
    *,
    min_width_pt: float = BARCODE_MIN_WIDTH_PT,
    target_width_ratio: float = BARCODE_TARGET_WIDTH_RATIO,
    min_height_ratio: float = BARCODE_MIN_HEIGHT_RATIO,
) -> bool:
    """
    Phóng to barcode và/hoặc QR code nếu nhỏ hơn ngưỡng cấu hình.
    Barcode/QR đã đủ lớn sẽ được bỏ qua.
    """
    if not BARCODE_ENLARGE_ENABLED and not QR_ENLARGE_ENABLED:
        return False

    doc = fitz.open(pdf_path)
    changed = False

    for page in doc:
        if BARCODE_ENLARGE_ENABLED:
            target_width = max(min_width_pt, page.rect.width * target_width_ratio)
            target_height = page.rect.height * min_height_ratio

            image_bc = _find_image_barcode(page)
            if image_bc:
                rect, xref = image_bc
                if rect.width < target_width * 0.95 or rect.height < target_height * 0.95:
                    img_bytes = doc.extract_image(xref)["image"]
                    scale_w = target_width / rect.width
                    scale_h = target_height / rect.height
                    scale = max(scale_w, scale_h)
                    _replace_enlarged_image(
                        page, rect, image_bytes=img_bytes,
                        new_width=rect.width * scale, new_height=rect.height * scale,
                    )
                    changed = True
            else:
                vector_rect = _find_vector_barcode_rect(page)
                if vector_rect and _enlarge_barcode_region(page, vector_rect, target_width, target_height):
                    changed = True

        if QR_ENLARGE_ENABLED:
            target_qr = max(QR_MIN_SIZE_PT, page.rect.width * QR_TARGET_SIZE_RATIO)
            if _enlarge_qr_on_page(page, doc, target_qr):
                changed = True

    if changed:
        tmp_path = f"{pdf_path}.tmp"
        doc.save(tmp_path, deflate=True)
        doc.close()
        os.replace(tmp_path, pdf_path)
        log_success(f"Da phong to barcode/QR: {pdf_path}")
        return True

    doc.close()
    return False
