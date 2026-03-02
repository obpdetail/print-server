# -*- coding: utf-8 -*-
"""
scan_pdf.py
Quét file PDF và trích xuất thông tin đơn hàng từng trang.
Sử dụng core/parsers để xử lý theo từng loại ĐVVC / nền tảng.
"""

import sys
from pathlib import Path

import pandas as pd
import pdfplumber

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from core.parsers import dispatch_page


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
            words     = page.extract_words()

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
    merged_pdf_path = "uploads/20260301_121951_02-28_23-09-21_Shipping label+Packing slip.pdf"
    df_orders, unrecognized = scan_pdf_for_orders(merged_pdf_path)
    print(df_orders)
    if unrecognized:
        print(f"\n⚠️  {len(unrecognized)} trang không nhận dạng được:")
        for p in unrecognized:
            dvvc = p["delivery_method"] or "Không rõ"
            sn   = p["order_sn"] or "—"
            print(f"  Trang {p['page_number']} - {dvvc} - {sn}")