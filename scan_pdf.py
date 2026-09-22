# -*- coding: utf-8 -*-
"""
scan_pdf.py
Quét file PDF và trích xuất thông tin đơn hàng từng trang.
Sử dụng core/parsers để xử lý theo từng loại ĐVVC / nền tảng.

Nếu trang không có text layout (PDF ảnh):
  - OCR bằng Tesseract (lang=vie)
  - Bổ sung giá trị barcode/QR detect được vào text để parser dùng

Nếu không nhận diện được ĐVVC nhưng có QR/barcode:
  - Vẫn lưu bản ghi (order_sn = null, QR lưu ở file_page_barcodes)
"""

import sys
from pathlib import Path

import pandas as pd
import pdfplumber

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from core.parsers import dispatch_page
from core.pdf_barcodes import read_barcodes_on_pdf_page
from core.pdf_ocr import ocr_pdf_page, page_has_text_layout


def _append_barcode_texts(full_text: str, pairs: list[tuple[str, str]]) -> str:
    """Ghép mã barcode/QR vào text để parser nhận SPXVN… chính xác hơn OCR."""
    if not pairs:
        return full_text
    lines = [full_text.rstrip()] if full_text.strip() else []
    lines.append("")
    lines.append("--- BARCODES ---")
    for text, sym in pairs:
        lines.append(f"{sym}: {text}" if sym else text)
    return "\n".join(lines)


def _pick_qr_or_first(pairs: list[tuple[str, str]]) -> str | None:
    """Ưu tiên mã QR; không có thì lấy barcode đầu tiên."""
    if not pairs:
        return None
    for text, sym in pairs:
        if text and sym and "QR" in str(sym).upper():
            return text.strip()
    for text, _sym in pairs:
        if text and str(text).strip():
            return str(text).strip()
    return None


def _ensure_page_barcodes(
    pdf_path: str,
    page_number: int,
    existing: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    if existing:
        return existing
    try:
        return read_barcodes_on_pdf_page(pdf_path, page_number, max_codes=10)
    except Exception as e:
        print(f"Page {page_number}: ⚠️  Detect barcode/QR lỗi — {e}")
        return []


def scan_pdf_for_orders(merged_pdf_path: str):
    """
    Quét file PDF, trả về tuple (DataFrame, unrecognized_pages).

    DataFrame có các cột:
        page, order_sn, shop_name, platform,
        delivery_method, delivery_method_raw

    unrecognized_pages là list[dict] với các trang không nhận dạng được, mỗi phần tử:
        {"page_number": int, "delivery_method": str|None, "order_sn": str|None}
    """
    rows = []
    unrecognized = []
    with pdfplumber.open(merged_pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            full_text = page.extract_text(layout=True) or ""
            words = page.extract_words() or []

            page_barcodes: list[tuple[str, str]] = []
            if not page_has_text_layout(full_text, words):
                # PDF ảnh: OCR tiếng Việt + detect barcode/QR
                try:
                    ocr_text = ocr_pdf_page(merged_pdf_path, i)
                except Exception as e:
                    print(f"Page {i}: ⚠️  OCR lỗi — {e}")
                    ocr_text = ""
                page_barcodes = _ensure_page_barcodes(merged_pdf_path, i, [])
                full_text = _append_barcode_texts(ocr_text, page_barcodes)
                words = []
                if ocr_text or page_barcodes:
                    print(
                        f"Page {i}: 🖼️  PDF ảnh → OCR(vie)"
                        f" + {len(page_barcodes)} barcode/QR"
                    )

            result = dispatch_page(i, full_text, words, page)

            if result is not None and result.order_sn:
                print(
                    f"Page {i}: [{result.platform.upper()} / {result.delivery_method_raw or result.delivery_method}]"
                    f"  order={result.order_sn}  shop={result.shop_name}"
                )
                rows.append({
                    "page":                result.page_number,
                    "order_sn":            result.order_sn,
                    "shop_name":           result.shop_name,
                    "platform":            result.platform,
                    "delivery_method":     result.delivery_method,
                    "delivery_method_raw": result.delivery_method_raw,
                })
                continue

            # Chưa có mã đơn → quét QR; mã đơn để null, QR lưu ở file_page_barcodes
            page_barcodes = _ensure_page_barcodes(merged_pdf_path, i, page_barcodes)
            qr_or_code = _pick_qr_or_first(page_barcodes)

            if qr_or_code:
                if result is not None:
                    print(
                        f"Page {i}: [{result.platform.upper()} / {result.delivery_method_raw or result.delivery_method}]"
                        f"  order=null  qr={qr_or_code}  shop={result.shop_name}"
                    )
                    rows.append({
                        "page":                result.page_number,
                        "order_sn":            None,
                        "shop_name":           result.shop_name,
                        "platform":            result.platform,
                        "delivery_method":     result.delivery_method,
                        "delivery_method_raw": result.delivery_method_raw,
                    })
                else:
                    print(
                        f"Page {i}: ⚠️  Chưa nhận diện ĐVVC — lưu QR (mã đơn=null): {qr_or_code}"
                    )
                    rows.append({
                        "page":                i,
                        "order_sn":            None,
                        "shop_name":           None,
                        "platform":            "unknown",
                        "delivery_method":     None,
                        "delivery_method_raw": None,
                    })
                continue

            if result is None:
                print(f"Page {i}: ⚠️  Không nhận dạng được ĐVVC — bỏ qua")
                unrecognized.append({
                    "page_number":     i,
                    "delivery_method": None,
                    "order_sn":        None,
                })
            else:
                print(
                    f"Page {i}: ⚠️  Nhận dạng được "
                    f"[{result.delivery_method_raw or result.delivery_method}] "
                    f"nhưng không lấy được mã đơn/QR — bỏ qua"
                )
                unrecognized.append({
                    "page_number":     i,
                    "delivery_method": result.delivery_method_raw or result.delivery_method or None,
                    "order_sn":        None,
                })

    return pd.DataFrame(rows), unrecognized


if __name__ == "__main__":
    merged_pdf_path = "test-files/2029-09-19-4.pdf"
    df_orders, unrecognized = scan_pdf_for_orders(merged_pdf_path)
    print(df_orders)
    if unrecognized:
        print(f"\n⚠️  {len(unrecognized)} trang không nhận dạng được:")
        for p in unrecognized:
            dvvc = p["delivery_method"] or "Không rõ"
            sn   = p["order_sn"] or "—"
            print(f"  Trang {p['page_number']} - {dvvc} - {sn}")
