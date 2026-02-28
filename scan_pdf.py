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


def scan_pdf_for_orders(merged_pdf_path: str) -> pd.DataFrame:
    """
    Quét file PDF, trả về DataFrame với các cột:
        page, order_sn, shop_name, platform,
        delivery_method, delivery_method_raw

    Backward-compatible: code cũ chỉ dùng page/order_sn/shop_name/delivery_method
    vẫn hoạt động bình thường.
    """
    rows = []
    with pdfplumber.open(merged_pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            full_text = page.extract_text(layout=True) or ""
            words     = page.extract_words()

            result = dispatch_page(i, full_text, words, page)

            if result is None:
                print(f"Page {i}: ⚠️  Không nhận dạng được ĐVVC — bỏ qua")
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

    return pd.DataFrame(rows)


if __name__ == "__main__":
    merged_pdf_path = r"C:\Users\Desk Top\Dropbox\OBP\Code\OBP-GetData\OUTPUT_PDF\reordered_pdf_20260227_150339.pdf"
    df_orders = scan_pdf_for_orders(merged_pdf_path)
    print(df_orders)