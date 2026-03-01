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
import re

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
            match_delivery_id = re.search(r"Mã\s*[vV]ận\s*[đĐ]ơn\s*:\s*(\S+)", full_text, flags=re.IGNORECASE)
            delivery_id = match_delivery_id.group(1) if match_delivery_id else None
            # package_id chỉ có trên tiktok j&t (đã loại bỏ từ hóa đơn)
            # match_package_id = re.search(r"Package\s*ID\s*:\s*(\S+)", full_text, flags=re.IGNORECASE)
            # package_id = match_package_id.group(1) if match_package_id else None
            print(f"Page {i}: delivery_id = {delivery_id}")

            if delivery_id:
                if delivery_id.startswith("SPX"):
                    delivery_method = "SPX"
                elif delivery_id.startswith("GY"):
                    delivery_method = "GHN"
                elif delivery_id.startswith("SHOPEEVTPVN"):
                    delivery_method = "VTP"
                elif delivery_id.startswith("EK"):
                    delivery_method = "VNP"
            # Nếu không tìm thấy "mã vận đơn", kiểm tra xem có chữ J&T trong hóa đơn
            elif "J&T" in full_text or "J & T" in full_text:
                jnt_match = re.search(r"(\d{12})", full_text)
                delivery_id = jnt_match.group(1) if jnt_match else None
                delivery_method = "JT"
            else:
                delivery_method = "HT"  # Hỏa tốc

            match_order_id = re.search(r"Mã\s*[đd]ơn\s*hàng\s*:\s*(\S+)", full_text, flags=re.IGNORECASE) or re.search(r"Order\s*ID\s*:\s*(\S+)", full_text, flags=re.IGNORECASE)
            order_id = str(match_order_id.group(1)) if match_order_id else None

            # --- Tìm toạ độ và shop name theo từng delivery method ---
            words = page.extract_words()
            den_x0 = None
            tu_y1 = None
            shop_words = []
            found_line = False

            if delivery_method == "JT":
                # Sử dụng regex để tìm tên shop ngay sau "Người gửi"
                # Pattern: "Người gửi" + có thể có khoảng trắng/xuống dòng + tên shop (1-3 từ)
                shop_match = re.search(r"Người\s+gửi\s*[\n\r\s]*([^\n\r]+?)(?=\n|\r|Căn|Số|Phường|Xã|Quận|Huyện|Thành phố|[0-9])", full_text, re.IGNORECASE)
                
                if shop_match:
                    shop_name_raw = shop_match.group(1).strip()
                    # Loại bỏ các ký tự đặc biệt, số dư thừa
                    # Chỉ giữ lại phần text chính 
                    shop_parts = shop_name_raw.split()
                    # Lọc bỏ các phần tử chứa nhiều số hoặc ký tự đặc biệt
                    filtered_parts = []
                    for part in shop_parts:
                        # Nếu phần tử chứa ít hơn 50% số thì giữ lại
                        digit_count = sum(c.isdigit() for c in part)
                        if len(part) == 0 or digit_count / len(part) < 0.5:
                            filtered_parts.append(part)
                        else:
                            break  # Dừng khi gặp phần có nhiều số (thường là địa chỉ)
                    
                    shop_words = filtered_parts if filtered_parts else [shop_name_raw]
                else:
                    shop_words = ["UNKNOWN_SHOP"]

            elif delivery_method == "VTP":
                # Bước 1: Tìm x0 của "Đến"
                for w in words:
                    if "Đến" in w['text']:
                        den_x0 = w['x0']
                        break

                # Bước 2: Tìm y1 của dòng chứa "Từ"
                for w in words:
                    if "Từ" in w['text']:
                        tu_y1 = w['bottom']
                        break

            else:  # SPX, GHN, VNP, HT (dùng "Từ:" / "Đến:")
                # Bước 1: Tìm x0 của "Đến:"
                for w in words:
                    if "Đến:" in w['text']:
                        den_x0 = w['x0']
                        break

                # Bước 2: Tìm y1 của dòng chứa "Từ:"
                for w in words:
                    if "Từ:" in w['text']:
                        tu_y1 = w['bottom']
                        break

            # Bước 3: Lấy dòng ngay dưới "Từ:" và chỉ lấy phần có x0 < Đến:
            if den_x0 and tu_y1:
                for w in words:
                    # Dòng ngay dưới (trong khoảng 20px)
                    if tu_y1 < w['top'] < tu_y1 + 20:
                        if w['x0'] < den_x0:
                            shop_words.append(w['text'])
                            found_line = True
                        elif found_line:
                            break  # Dừng lại nếu gặp từ nằm sau "Đến:"
            elif delivery_method != "JT" and not shop_words:
                shop_words.append("UNKNOWN_SHOP")

            shop_name = " ".join(shop_words).strip()

            # Debug: In thông tin tìm được
            print(f"   → Order: {order_id}, Shop: {shop_name}, Method: {delivery_method}")

            if order_id:
                rows.append({
                    "page":                i,
                    "order_sn":            order_id,
                    "shop_name":           shop_name,
                    "platform":            None,  # Có thể thêm logic xác định platform sau
                    "delivery_method":     delivery_method,
                    "delivery_method_raw": delivery_method,
                })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    merged_pdf_path = "uploads/20260301_122437_02-28_23-09-21_Shipping label+Packing slip.pdf"
    df_orders = scan_pdf_for_orders(merged_pdf_path)
    print(df_orders)