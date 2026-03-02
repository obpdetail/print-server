"""
compare_orders.py
-----------------
So sánh danh sách đơn hàng giữa 2 thư mục chứa file PDF.
Mỗi thư mục có thể chứa nhiều file PDF, mỗi file là danh sách phiếu đơn hàng.

Cách dùng:
    python compare_orders.py <folder_A> <folder_B>
    python compare_orders.py          ← sẽ hỏi đường dẫn thủ công
"""

import sys
import os
from pathlib import Path

# Thêm thư mục gốc vào sys.path để import scan_pdf
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from scan_pdf import scan_pdf_for_orders


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def scan_folder(folder: str) -> pd.DataFrame:
    """Quét tất cả file PDF trong folder và gộp kết quả thành 1 DataFrame."""
    folder_path = Path(folder)
    if not folder_path.is_dir():
        raise ValueError(f"Không tìm thấy thư mục: {folder}")

    pdf_files = sorted(folder_path.glob("*.pdf"))
    if not pdf_files:
        print(f"  [!] Không có file PDF nào trong: {folder}")
        return pd.DataFrame(columns=["order_sn", "shop_name", "delivery_method", "page", "source_file"])

    all_dfs = []
    for pdf_file in pdf_files:
        print(f"  Đang đọc: {pdf_file.name} ...")
        try:
            df, _ = scan_pdf_for_orders(str(pdf_file))
            df["source_file"] = pdf_file.name
            all_dfs.append(df)
        except Exception as e:
            print(f"  [!] Lỗi khi đọc {pdf_file.name}: {e}")

    if not all_dfs:
        return pd.DataFrame(columns=["order_sn", "shop_name", "delivery_method", "page", "source_file"])

    combined = pd.concat(all_dfs, ignore_index=True)
    # Xoá trùng lặp theo order_sn (giữ lần xuất hiện đầu tiên)
    combined = combined.drop_duplicates(subset=["order_sn"])
    return combined


def print_separator(char="─", width=70):
    print(char * width)


def compare_folders(folder_a: str, folder_b: str):
    folder_a = folder_a.strip().strip('"').strip("'")
    folder_b = folder_b.strip().strip('"').strip("'")

    print()
    print_separator("═")
    print("  SO SÁNH DANH SÁCH ĐƠN HÀNG GIỮA 2 THƯ MỤC")
    print_separator("═")
    print(f"  Thư mục A : {folder_a}")
    print(f"  Thư mục B : {folder_b}")
    print_separator()

    print("\n[1/2] Quét thư mục A ...")
    df_a = scan_folder(folder_a)
    print(f"  → {len(df_a)} đơn hàng tìm được trong thư mục A")

    print("\n[2/2] Quét thư mục B ...")
    df_b = scan_folder(folder_b)
    print(f"  → {len(df_b)} đơn hàng tìm được trong thư mục B")

    # ── So sánh ──────────────────────────────────────────────
    set_a = set(df_a["order_sn"].dropna())
    set_b = set(df_b["order_sn"].dropna())

    common      = set_a & set_b          # có ở cả 2
    only_in_a   = set_a - set_b          # chỉ có ở A
    only_in_b   = set_b - set_a          # chỉ có ở B

    # ── Kết quả tổng quan ────────────────────────────────────
    print()
    print_separator("═")
    print("  KẾT QUẢ SO SÁNH")
    print_separator("═")
    print(f"  Tổng đơn trong A        : {len(set_a):>6}")
    print(f"  Tổng đơn trong B        : {len(set_b):>6}")
    print_separator()
    print(f"  Đơn GIỐNG NHAU (A ∩ B)  : {len(common):>6}")
    print(f"  Đơn CHỈ CÓ trong A      : {len(only_in_a):>6}")
    print(f"  Đơn CHỈ CÓ trong B      : {len(only_in_b):>6}")
    print_separator()

    # ── Chi tiết đơn chỉ có ở A ──────────────────────────────
    if only_in_a:
        df_only_a = (
            df_a[df_a["order_sn"].isin(only_in_a)]
            .sort_values("order_sn")
            [["order_sn", "shop_name", "delivery_method", "source_file"]]
            .reset_index(drop=True)
        )
        df_only_a.index += 1
        print(f"\n  ĐƠN CHỈ CÓ TRONG A ({len(only_in_a)} đơn):")
        print_separator("-")
        print(df_only_a.to_string())
        print()

    # ── Chi tiết đơn chỉ có ở B ──────────────────────────────
    if only_in_b:
        df_only_b = (
            df_b[df_b["order_sn"].isin(only_in_b)]
            .sort_values("order_sn")
            [["order_sn", "shop_name", "delivery_method", "source_file"]]
            .reset_index(drop=True)
        )
        df_only_b.index += 1
        print(f"\n  ĐƠN CHỈ CÓ TRONG B ({len(only_in_b)} đơn):")
        print_separator("-")
        print(df_only_b.to_string())
        print()

    if not only_in_a and not only_in_b:
        print("\n  ✓ Hai thư mục có cùng danh sách đơn hàng hoàn toàn.")

    print_separator("═")
    print()

    # ── Trả về dict để tái sử dụng khi import ────────────────
    return {
        "df_a": df_a,
        "df_b": df_b,
        "common": common,
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
    }


# ─────────────────────────────────────────────────────────────
#  Entrypoint
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    folder_a = r"G:\My Drive\obp\PDF_Grouped\2026-02-27-14-48-59"
    folder_b = r"G:\My Drive\obp\PDF_Grouped\2026-02-27-14-49-38"

    compare_folders(folder_a, folder_b)
