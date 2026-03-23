# -*- coding: utf-8 -*-
"""
sample/send_files_to_print.py
──────────────────────────────
Demo gửi danh sách file PDF đến In file PDF qua REST API.

Các bước thực hiện:
  1. Lấy danh sách máy in khả dụng  (GET  /api/printers)
  2. Upload từng file PDF            (POST /api/upload)
  3. Gửi lệnh in cho từng file       (POST /api/print)
  4. Kiểm tra lịch sử in             (GET  /api/jobs)

Yêu cầu:
  pip install requests
"""

import sys
from pathlib import Path
import requests

# ── Cấu hình ─────────────────────────────────────────────────────────────────

SERVER_URL   = "http://localhost:5000"   # Địa chỉ In file PDF
PRINTER_NAME = ""                        # Để trống → dùng máy in mặc định
COPIES       = 1                         # Số bản in cho mỗi file
PRINT_FOLDER = r"I:\My Drive\in-don\test"                # Thư mục chứa file PDF cần in

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_printers(base_url: str) -> dict:
    """Lấy danh sách máy in và máy in mặc định từ server."""
    resp = requests.get(f"{base_url}/api/printers", timeout=10)
    resp.raise_for_status()
    return resp.json()


def upload_file(base_url: str, file_path: str) -> str:
    """
    Upload một file PDF lên server.
    Trả về tên file sau khi đã lưu trên server (dùng để gửi lệnh in).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File không tồn tại: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Chỉ hỗ trợ file PDF: {file_path}")

    with open(path, "rb") as f:
        resp = requests.post(
            f"{base_url}/api/upload",
            files={"file": (path.name, f, "application/pdf")},
            timeout=60,
        )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Upload thất bại: {data.get('error')}")
    return data["filename"]   # tên file đã lưu trên server


def send_print(base_url: str, server_filename: str,
               printer: str = "", copies: int = 1) -> dict:
    """
    Gửi lệnh in cho file đã upload.
    Trả về thông tin job in.
    """
    payload = {
        "filename": server_filename,
        "printer":  printer,
        "copies":   copies,
    }
    resp = requests.post(f"{base_url}/api/print", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"In thất bại: {data.get('error')}")
    return data.get("job", {})


def get_recent_jobs(base_url: str, limit: int = 10) -> list:
    """Lấy lịch sử in gần nhất."""
    resp = requests.get(f"{base_url}/api/jobs", timeout=10)
    resp.raise_for_status()
    return resp.json().get("jobs", [])[:limit]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    PDF_FILES = [str(p) for p in Path(PRINT_FOLDER).glob("*.pdf")]
    if not PDF_FILES:
        print(f"❌ Không tìm thấy file PDF nào trong thư mục: {PRINT_FOLDER}")
        sys.exit(1)

    print(f"🔗 Kết nối đến In file PDF: {SERVER_URL}\n")

    # 1. Danh sách máy in ─────────────────────────────────────────────────────
    try:
        info = get_printers(SERVER_URL)
        printers = info.get("printers", [])
        default  = info.get("default", "")
        print(f"🖨️  Máy in khả dụng ({len(printers)}):")
        for p in printers:
            marker = " ← mặc định" if p["id"] == default else ""
            print(f"   • {p['label']} ({p['id']}){marker}")
        print()
    except Exception as e:
        print(f"❌ Không thể lấy danh sách máy in: {e}")
        sys.exit(1)

    # Xác định máy in sẽ dùng
    target_printer = PRINTER_NAME or default
    print(f"✅ Sẽ in bằng máy: {target_printer or '(mặc định hệ thống)'}\n")

    # 2 & 3. Upload + In từng file ────────────────────────────────────────────
    results = []
    for local_path in PDF_FILES:
        print(f"📄 Xử lý: {local_path}")
        try:
            # Upload
            server_name = upload_file(SERVER_URL, local_path)
            print(f"   ✔ Upload OK → {server_name}")

            # In
            job = send_print(SERVER_URL, server_name,
                             printer=target_printer, copies=COPIES)
            print(f"   ✔ Gửi lệnh in OK | Job ID: {job.get('id')} "
                  f"| {COPIES} bản | {job.get('time')}")
            results.append({"file": local_path, "job": job, "ok": True})

        except FileNotFoundError as e:
            print(f"   ✘ {e}")
            results.append({"file": local_path, "ok": False, "error": str(e)})
        except Exception as e:
            print(f"   ✘ Lỗi: {e}")
            results.append({"file": local_path, "ok": False, "error": str(e)})
        print()

    # 4. Tóm tắt ──────────────────────────────────────────────────────────────
    total   = len(results)
    success = sum(1 for r in results if r["ok"])
    failed  = total - success

    print("─" * 50)
    print(f"📊 Kết quả: {success}/{total} file in thành công"
          + (f", {failed} thất bại" if failed else ""))

    if failed:
        print("\nCác file lỗi:")
        for r in results:
            if not r["ok"]:
                print(f"  • {r['file']} → {r['error']}")

    # 5. Lịch sử in gần nhất ─────────────────────────────────────────────────
    print("\n📋 Lịch sử 5 lệnh in gần nhất:")
    try:
        jobs = get_recent_jobs(SERVER_URL, limit=5)
        for j in jobs:
            icon = "✔" if j.get("status") == "success" else "✘"
            print(f"  {icon} [{j['time']}] {j['filename']} → {j['printer']} | {j['status']}")
    except Exception as e:
        print(f"  Không thể tải lịch sử: {e}")


if __name__ == "__main__":
    main()
