# -*- coding: utf-8 -*-
"""
gsheet_helper.py  –  Google Sheets Integration
Các hàm hỗ trợ lấy dữ liệu từ Google Sheets thay thế cho OMS API.
"""

import os
from pathlib import Path

from error_handler import log_error

# load env
from dotenv import load_dotenv
load_dotenv()


BASE_DIR = Path(__file__).parent


def _gsheet_init():
    """
    Khởi tạo kết nối Google Sheets.
    Yêu cầu:
      - File credentials JSON: GOOGLE_CREDENTIALS_PATH (env hoặc mặc định)
      - Google Spreadsheet ID: GOOGLE_SHEET_ID (env)
    Trả về: gspread.Spreadsheet object
    """
    try:
        import gspread
    except ImportError:
        raise Exception(
            "Thiếu thư viện gspread. Cài đặt: pip install gspread google-auth"
        )
    
    creds_path = os.environ.get(
        "GOOGLE_CREDENTIALS_PATH",
        str(BASE_DIR / "google_credentials.json")
    )
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    
    if not sheet_id:
        raise Exception(
            "Thiếu GOOGLE_SHEET_ID trong biến môi trường. "
            "Thêm vào file .env hoặc thiết lập system environment."
        )
    
    if not Path(creds_path).exists():
        raise Exception(
            f"Không tìm thấy file credentials: {creds_path}. "
            "Tải về từ Google Cloud Console → Service Account → Create Key (JSON)."
        )
    
    # Kết nối bằng service_account - đơn giản hơn
    gc = gspread.service_account(filename=creds_path)
    spreadsheet = gc.open_by_key(sheet_id)
    
    return spreadsheet


def gsheet_get_shop_info(shop_name: str) -> dict:
    """
    Lấy thông tin shop từ Google Sheet.
    Sheet format (ví dụ tab "Shops"):
      | shop_name | shop_id | platform | ...
      |-----------|---------|----------|-----
      | Shop A    | 123     | Shopee   | ...
    
    Args:
        shop_name: Tên shop cần tìm
    
    Returns:
        {"shop_id": int, "shop_name": str, "platform": str, ...}
        
    Raises:
        Exception nếu không tìm thấy shop
    """
    try:
        spreadsheet = _gsheet_init()
        sheet_name = os.environ.get("GSHEET_SHOPS_TAB", "Shops")
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # Lấy tất cả dữ liệu dưới dạng list of dict (header = row 1)
        records = worksheet.get_all_records()
        
        # Tìm shop theo tên (case-insensitive)
        shop_name_lower = shop_name.strip().lower()
        for row in records:
            if row.get("shop_name", "").strip().lower() == shop_name_lower:
                return {
                    "shop_id": int(row.get("shop_id", 0)),
                    "shop_name": row.get("shop_name", ""),
                    "platform": row.get("platform", ""),
                }
        
        raise Exception(f"Không tìm thấy shop '{shop_name}' trong Google Sheet")
        
    except Exception as e:
        log_error("gsheet_get_shop_info", e, {"shop_name": shop_name})
        raise


def gsheet_get_product_warehouse_info(product_lookups: list[dict]) -> dict:
    """
    Lấy thông tin warehouse SKU và quantity từ Google Sheet.
    Sheet format (ví dụ tab "Products"):
      | shop_id | item_id | model_id | warehouse_sku | warehouse_quantity | item_name | model_name |
      |---------|---------|----------|---------------|-------------------|-----------|------------|
      | 123     | 456     | 789      | SKU-001       | 2                 | Áo        | Đỏ-M      |
    
    Args:
        product_lookups: [{"shop_id": int, "item_id": int, "model_id": int}, ...]
    
    Returns:
        {
            "found": [
                {"shop_id": 123, "item_id": 456, "model_id": 789,
                 "warehouse_sku": "SKU-001", "warehouse_quantity": 2,
                 "item_name": "Áo", "model_name": "Đỏ-M"},
                ...
            ],
            "not_found": [
                {"shop_id": 999, "item_id": 111, "model_id": 222},
                ...
            ]
        }
    """
    try:
        spreadsheet = _gsheet_init()
        sheet_name = os.environ.get("GSHEET_PRODUCTS_TAB", "Products")
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # Lấy tất cả dữ liệu
        records = worksheet.get_all_records()
        
        # Tạo index cho tra cứu nhanh: (shop_id, item_id, model_id) → row data
        product_map = {}
        for row in records:
            try:
                key = (
                    int(row.get("shop_id", 0)),
                    int(row.get("item_id", 0)),
                    int(row.get("model_id", 0))
                )
                product_map[key] = {
                    "warehouse_sku": row.get("warehouse_sku", "").strip(),
                    "warehouse_quantity": int(row.get("warehouse_quantity", 1)),
                    "item_name": row.get("item_name", "").strip(),
                    "model_name": row.get("model_name", "").strip(),
                }
            except (ValueError, TypeError):
                # Bỏ qua dòng có dữ liệu không hợp lệ
                continue
        
        found = []
        not_found = []
        
        for lookup in product_lookups:
            shop_id = int(lookup.get("shop_id", 0))
            item_id = int(lookup.get("item_id", 0))
            model_id = int(lookup.get("model_id", 0))
            key = (shop_id, item_id, model_id)
            
            if key in product_map:
                found.append({
                    "shop_id": shop_id,
                    "item_id": item_id,
                    "model_id": model_id,
                    **product_map[key]
                })
            else:
                not_found.append({
                    "shop_id": shop_id,
                    "item_id": item_id,
                    "model_id": model_id,
                })
        
        return {"found": found, "not_found": not_found}
        
    except Exception as e:
        log_error("gsheet_get_product_warehouse_info", e)
        raise


def gsheet_get_warehouse_sku(product_lookups: list[dict]) -> dict:
    """
    Tìm warehouse_sku theo danh sách shop/item/model từ Google Sheet tab "Item".
    
    Sheet "Item" format:
      | shop_id | Mã Sản phẩm | Tên Sản phẩm | Mã Phân loại | Tên phân loại | SKU Sản phẩm | SKU | Giá | GTIN | Số lượng | che_sku | che_qty |
      |---------|-------------|--------------|--------------|---------------|--------------|-----|-----|------|----------|---------|---------|
      | 123     | 456         | Áo thun      | 789          | Đỏ-M         | PROD-001     | WH-001 | 100 | ... | 2     | WH-CHE-001 | 3 |
    
    Mapping:
      - shop_id → shop_id
      - Mã Sản phẩm → item_id
      - Mã Phân loại → model_id
      - che_sku → warehouse_sku
      - che_qty → warehouse_quantity
      - Tên Sản phẩm → item_name
      - Tên phân loại → model_name
    
    Args:
        product_lookups: [{"shop_id": str|int, "item_id": str|int, "model_id": str|int}, ...]
    
    Returns:
        {
            "found": [
                {
                    "shop_id": "123",
                    "item_id": "456",
                    "model_id": "789",
                    "warehouse_sku": "WH-CHE-001",
                    "warehouse_quantity": 3
                },
                ...
            ],
            "not-found": [
                {"shop_id": "999", "item_id": "111", "model_id": "222"},
                ...
            ]
        }
    """
    try:
        spreadsheet = _gsheet_init()
        sheet_name = os.environ.get("GSHEET_ITEM_TAB", "Item")
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # Lấy tất cả dữ liệu
        records = worksheet.get_all_records()
        
        # Tạo index cho tra cứu nhanh: (shop_id, item_id, model_id) → row data
        item_map = {}
        for row in records:
            try:
                # Mapping cột từ sheet "Item"
                shop_id = str(row.get("shop_id", "")).strip()
                item_id = str(row.get("Mã Sản phẩm", "")).strip()
                model_id = str(row.get("Mã Phân loại", "")).strip()
                warehouse_sku = str(row.get("che_sku", "")).strip()  # ← Sửa từ "SKU" → "che_sku"
                
                if not shop_id or not item_id or not model_id:
                    continue  # Bỏ qua dòng thiếu thông tin
                
                key = (shop_id, item_id, model_id)
                
                # Chỉ lưu nếu có warehouse_sku
                if warehouse_sku:
                    item_map[key] = {
                        "warehouse_sku": warehouse_sku,
                        "warehouse_quantity": int(row.get("che_qty", 1)),  # ← Sửa từ "Số lượng" → "che_qty"
                        "item_name": str(row.get("Tên Sản phẩm", "")).strip(),
                        "model_name": str(row.get("Tên phân loại", "")).strip(),
                    }
            except (ValueError, TypeError) as err:
                # Bỏ qua dòng có dữ liệu không hợp lệ
                continue
        
        found = []
        not_found = []
        
        for lookup in product_lookups:
            # Convert to string for matching (giống OMS API)
            shop_id = str(lookup.get("shop_id", "")).strip()
            item_id = str(lookup.get("item_id", "")).strip()
            model_id = str(lookup.get("model_id", "")).strip()
            
            if not shop_id or not item_id or not model_id:
                not_found.append(lookup)
                continue
            
            key = (shop_id, item_id, model_id)
            
            if key in item_map:
                found.append({
                    "shop_id": shop_id,
                    "item_id": item_id,
                    "model_id": model_id,
                    "warehouse_sku": item_map[key]["warehouse_sku"],
                    "warehouse_quantity": item_map[key]["warehouse_quantity"],
                })
            else:
                not_found.append({
                    "shop_id": shop_id,
                    "item_id": item_id,
                    "model_id": model_id,
                })
        
        return {"found": found, "not-found": not_found}
        
    except Exception as e:
        log_error("gsheet_get_warehouse_sku", e)
        raise


def main():
    try:
        spreadsheet = _gsheet_init()
        print(f"Kết nối thành công đến Google Sheet: {spreadsheet.title}")
    except Exception as e:
        log_error("gsheet_get_warehouse_sku.main", e)
        raise

if __name__ == "__main__":
    main()
