# -*- coding: utf-8 -*-
"""
scan_pdf.py
Quét file PDF và trích xuất thông tin đơn hàng từng trang.
Sử dụng core/parsers để xử lý theo từng loại ĐVVC / nền tảng.

Nếu trang không có text layout (PDF ảnh):
  - OCR bằng Tesseract (lang=vie)
  - Bổ sung giá trị barcode/QR detect được vào text để parser dùng
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
                try:
                    page_barcodes = read_barcodes_on_pdf_page(
                        merged_pdf_path, i, max_codes=10
                    )
                except Exception as e:
                    print(f"Page {i}: ⚠️  Detect barcode/QR lỗi — {e}")
                    page_barcodes = []
                full_text = _append_barcode_texts(ocr_text, page_barcodes)
                words = []
                if ocr_text or page_barcodes:
                    print(
                        f"Page {i}: 🖼️  PDF ảnh → OCR(vie)"
                        f" + {len(page_barcodes)} barcode/QR"
                    )

            result = dispatch_page(i, full_text, words, page)

            if result is None:
                print(f"Page {i}: ⚠️  Không nhận dạng được ĐVVC — bỏ qua")
                unrecognized.append({
                    "page_number":     i,
                    "delivery_method": None,
                    "order_sn":        None,
                })
                continue

            print(
                f"Page {i}: [{result.platform.upper()} / {result.delivery_method_raw or result.delivery_method}]"
                f"  order={result.order_sn}  shop={result.shop_name}"
            )

            if result.order_sn:
                rows.append({
                    "page":                result.page_number,
                    "order_sn":            result.order_sn,
                    "shop_name":           result.shop_name,
                    "platform":            result.platform,
                    "delivery_method":     result.delivery_method,
                    "delivery_method_raw": result.delivery_method_raw,
                })
            else:
                # Parser nhận dạng được ĐVVC nhưng không trích xuất được mã đơn
                print(f"Page {i}: ⚠️  Nhận dạng được [{result.delivery_method_raw or result.delivery_method}] nhưng không lấy được mã đơn — bỏ qua")
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
