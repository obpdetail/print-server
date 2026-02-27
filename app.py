# -*- coding: utf-8 -*-
"""
app.py  –  Print Server
Chạy Flask trên 0.0.0.0 để các máy trong mạng LAN truy cập được.
"""

import os
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, request, jsonify, render_template,
    send_from_directory, abort
)

# Thêm thư mục gốc vào sys.path để import core & error_handler
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from error_handler import log_error, log_info, log_warning
from scan_pdf import scan_pdf_for_orders

# ── Cấu hình ────────────────────────────────────────────────────────────────
UPLOAD_FOLDER        = BASE_DIR / "uploads"
JOB_LOG_FILE         = BASE_DIR / "logs" / "jobs.json"
PRINTER_ALIASES_FILE = BASE_DIR / "printer_aliases.json"
ALLOWED_EXT          = {"pdf"}
MAX_FILE_MB   = 50

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
JOB_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_MB * 1024 * 1024


# ── Helpers ──────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def load_jobs() -> list:
    if JOB_LOG_FILE.exists():
        try:
            with open(JOB_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_jobs(jobs: list):
    with open(JOB_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def add_job(filename: str, printer: str, status: str, message: str = "") -> dict:
    jobs = load_jobs()
    job = {
        "id":       str(uuid.uuid4())[:8],
        "filename": filename,
        "printer":  printer,
        "status":   status,   # success | error
        "message":  message,
        "time":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    jobs.insert(0, job)
    save_jobs(jobs[:200])     # giữ 200 bản ghi gần nhất
    return job


def get_printers() -> list[str]:
    """Lấy danh sách máy in trên Windows qua win32print."""
    try:
        import win32print
        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return [p[2] for p in printers]
    except ImportError:
        log_warning("win32print không khả dụng – trả về danh sách rỗng.")
        return []
    except Exception as e:
        log_error("get_printers", e)
        return []


def get_default_printer() -> str:
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        return ""


def load_printer_aliases() -> dict:
    """Đọc alias: {"Beeprt BY-496": "Máy In Cắt", ...}"""
    if PRINTER_ALIASES_FILE.exists():
        try:
            with open(PRINTER_ALIASES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_printer_aliases(aliases: dict):
    with open(PRINTER_ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# --- Danh sách máy in --------------------------------------------------------

@app.route("/api/printers")
def api_printers():
    printers = get_printers()
    default  = get_default_printer()
    aliases  = load_printer_aliases()
    printer_list = [
        {"id": p, "label": aliases.get(p, p)}
        for p in printers
    ]
    return jsonify({"printers": printer_list, "default": default})


# --- Cấu hình alias máy in ---------------------------------------------------

@app.route("/api/printer-aliases", methods=["GET"])
def api_get_aliases():
    aliases  = load_printer_aliases()
    printers = get_printers()
    result   = [{"id": p, "alias": aliases.get(p, "")} for p in printers]
    return jsonify({"aliases": result})


@app.route("/api/printer-aliases", methods=["POST"])
def api_set_alias():
    data    = request.get_json(force=True) or {}
    printer = data.get("printer", "").strip()
    alias   = data.get("alias", "").strip()
    if not printer:
        return jsonify({"ok": False, "error": "Thiếu tên máy in."}), 400
    aliases = load_printer_aliases()
    if alias:
        aliases[printer] = alias
    else:
        aliases.pop(printer, None)   # alias rỗng → xóa mapping
    save_printer_aliases(aliases)
    log_info(f"Alias máy in: '{printer}' → '{alias or '(đã xóa)'}'")
    return jsonify({"ok": True})


@app.route("/api/printer-aliases/<path:printer>", methods=["DELETE"])
def api_delete_alias(printer):
    aliases = load_printer_aliases()
    if printer in aliases:
        del aliases[printer]
        save_printer_aliases(aliases)
        log_info(f"Đã xóa alias máy in: '{printer}'")
    return jsonify({"ok": True})


# --- Upload file -------------------------------------------------------------

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Không có file được gửi lên."}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "Tên file trống."}), 400

    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Chỉ chấp nhận file PDF."}), 400

    # Lưu với tên gốc, thêm timestamp để tránh trùng
    safe_name = Path(file.filename).name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{timestamp}_{safe_name}"
    dest = UPLOAD_FOLDER / unique_name
    file.save(str(dest))
    log_info(f"Upload thành công: {unique_name}")

    return jsonify({"ok": True, "filename": unique_name})


# --- Danh sách file đã upload ------------------------------------------------

@app.route("/api/files")
def api_files():
    files = []
    for p in sorted(UPLOAD_FOLDER.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() == ".pdf":
            files.append({
                "name":    p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "time":    datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return jsonify({"files": files})


# --- Xóa file ----------------------------------------------------------------

@app.route("/api/files/<path:filename>", methods=["DELETE"])
def api_delete_file(filename):
    target = UPLOAD_FOLDER / filename
    if not target.exists():
        return jsonify({"ok": False, "error": "File không tồn tại."}), 404
    target.unlink()
    log_info(f"Đã xóa file: {filename}")
    return jsonify({"ok": True})


# --- Preview / download file -------------------------------------------------

@app.route("/api/files/<path:filename>", methods=["GET"])
def api_download_file(filename):
    return send_from_directory(str(UPLOAD_FOLDER), filename)


# --- Gửi lệnh in -------------------------------------------------------------

@app.route("/api/print", methods=["POST"])
def api_print():
    data     = request.get_json(force=True) or {}
    filename = data.get("filename", "").strip()
    printer  = data.get("printer", "").strip()
    copies   = int(data.get("copies", 1))

    if not filename:
        return jsonify({"ok": False, "error": "Thiếu tên file."}), 400

    filepath = UPLOAD_FOLDER / filename
    if not filepath.exists():
        return jsonify({"ok": False, "error": f"File không tồn tại: {filename}"}), 404

    # Quét PDF để lấy thông tin đơn hàng
    orders_info = []
    try:
        df_orders = scan_pdf_for_orders(str(filepath))
        if not df_orders.empty:
            orders_info = df_orders.to_dict('records')
            log_dir = BASE_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            # write append to json file
            with open(log_dir / "orders_log.json", "a", encoding="utf-8") as f:
                for order in orders_info:
                    log_entry = {
                        "filename": filename,
                        "order_sn": order.get("order_sn"),
                        "shop_name": order.get("shop_name"),
                        "delivery_method": order.get("delivery_method"),
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        else:
            log_warning(f"Không tìm thấy đơn hàng nào trong {filename}")
    except Exception as e:
        log_error("scan_pdf_for_orders", e, {"filename": filename})
        # Vẫn tiếp tục in dù quét lỗi

    # Gọi hàm in từ core/printing.py
    try:
        sys.path.insert(0, str(BASE_DIR / "core"))
        from printing import print_pdf_printer

        success = True
        for i in range(max(1, copies)):
            ok = print_pdf_printer(str(filepath), printer or None)
            if not ok:
                success = False
                break

        if success:
            orders_summary = f"{len(orders_info)} đơn hàng" if orders_info else "Không xác định đơn hàng"
            log_info(f"In thành công: {filename} → {printer or 'Default'} x{copies} ({orders_summary})")
            job = add_job(filename, printer or "Default", "success", f"{copies} bản in - {orders_summary}")
            return jsonify({"ok": True, "job": job, "orders": orders_info})
        else:
            msg = (
                "Gửi lệnh in thất bại. "
                "Gợi ý: Cài SumatraPDF (https://www.sumatrapdfreader.org) "
                "hoặc Adobe Acrobat Reader để in PDF tốt hơn."
            )
            add_job(filename, printer or "Default", "error", msg)
            return jsonify({"ok": False, "error": msg}), 500

    except Exception as e:
        log_error("api_print", e, {"filename": filename, "printer": printer})
        msg = str(e)
        add_job(filename, printer or "Default", "error", msg)
        return jsonify({"ok": False, "error": msg}), 500


# --- Lịch sử in --------------------------------------------------------------

@app.route("/api/jobs")
def api_jobs():
    return jsonify({"jobs": load_jobs()})


# --- Thông tin máy chủ -------------------------------------------------------

@app.route("/api/info")
def api_info():
    import socket
    hostname  = socket.gethostname()
    local_ip  = socket.gethostbyname(hostname)
    return jsonify({
        "hostname": hostname,
        "ip":       local_ip,
        "port":     PORT,
    })


# ── Entry point ──────────────────────────────────────────────────────────────

PORT = int(os.environ.get("PRINT_SERVER_PORT", 5000))

if __name__ == "__main__":
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    print("=" * 60)
    print("  🖨️  PRINT SERVER đang chạy")
    print(f"  Local  : http://localhost:{PORT}")
    print(f"  Mạng LAN: http://{local_ip}:{PORT}")
    print("  Nhấn Ctrl+C để dừng")
    print("=" * 60)

    app.run(host="0.0.0.0", port=PORT, debug=False)
