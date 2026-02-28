# -*- coding: utf-8 -*-
"""
app.py  –  Print Server
Chạy Flask trên 0.0.0.0 để các máy trong mạng LAN truy cập được.
"""

import os
import sys
import uuid
import json
from datetime import datetime, timezone
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
from database import init_db, get_session, UploadedFile, PrintJob, OrderPrint

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

# Khởi tạo database (tạo DB + bảng nếu chưa có)
try:
    init_db()
    log_info("Database initialized.")
except Exception as _db_err:
    log_error("init_db", _db_err)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Trả về datetime UTC không có tzinfo (để lưu vào MySQL DATETIME)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

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

    original_name = Path(file.filename).name
    timestamp     = _utcnow().strftime("%Y%m%d_%H%M%S")
    unique_name   = f"{timestamp}_{original_name}"
    dest          = UPLOAD_FOLDER / unique_name
    file.save(str(dest))

    file_size_kb = int(round(dest.stat().st_size / 1024, 0))
    upload_ip    = request.remote_addr
    now_utc      = _utcnow()

    # ── Ghi vào DB ──────────────────────────────────────────────
    try:
        with get_session() as db:
            db.add(UploadedFile(
                filename=unique_name,
                original_name=original_name,
                upload_time_utc=now_utc,
                upload_ip=upload_ip,
                file_size_kb=file_size_kb,
            ))
    except Exception as e:
        log_error("api_upload.db", e, {"filename": unique_name})

    log_info(f"Upload: {unique_name} từ {upload_ip} ({file_size_kb} KB)")

    # ── Quét PDF → kiểm tra đơn trùng (Feature 6) ───────────────
    upload_warnings = []
    try:
        df_orders = scan_pdf_for_orders(str(dest))
        if not df_orders.empty:
            order_sns = df_orders["order_sn"].dropna().tolist()
            if order_sns:
                with get_session() as db:
                    existing = db.query(OrderPrint).filter(
                        OrderPrint.order_sn.in_(order_sns)
                    ).all()
                    for op in existing:
                        upload_warnings.append({
                            "order_sn":        op.order_sn,
                            "shop_name":       op.shop_name,
                            "platform":        op.platform,
                            "delivery_method": op.delivery_method,
                            "print_count":     op.print_count,
                            "last_print_time": (
                                op.last_print_time_utc.strftime("%Y-%m-%d %H:%M:%S")
                                if op.last_print_time_utc else None
                            ),
                        })
    except Exception as e:
        log_error("api_upload.scan", e, {"filename": unique_name})

    return jsonify({
        "ok":              True,
        "filename":        unique_name,
        "upload_warnings": upload_warnings,
    })


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

@app.route("/api/print/check", methods=["POST"])
def api_print_check():
    """Kiểm tra trước khi in: trả về cảnh báo nếu file/đơn đã in trước đó."""
    data     = request.get_json(force=True) or {}
    filename = data.get("filename", "").strip()

    if not filename:
        return jsonify({"ok": False, "error": "Thiếu tên file."}), 400

    filepath = UPLOAD_FOLDER / filename
    if not filepath.exists():
        return jsonify({"ok": False, "error": f"File không tồn tại: {filename}"}), 404

    result = {"ok": True, "has_warnings": False, "file_warnings": None, "order_warnings": []}

    # ── Kiểm tra file đã in chưa ─────────────────────────────────
    try:
        with get_session() as db:
            prev_jobs = (
                db.query(PrintJob)
                .filter(PrintJob.filename == filename, PrintJob.status == "success")
                .order_by(PrintJob.print_time_utc.desc())
                .all()
            )
            if prev_jobs:
                result["has_warnings"] = True
                latest = prev_jobs[0]
                result["file_warnings"] = {
                    "print_count":     len(prev_jobs),
                    "last_print_time": (
                        latest.print_time_utc.strftime("%Y-%m-%d %H:%M:%S")
                        if latest.print_time_utc else None
                    ),
                    "last_printer":    latest.printer_name,
                    "last_client_ip":  latest.client_ip,
                }
    except Exception as e:
        log_error("api_print_check.file", e)

    # ── Quét PDF → kiểm tra từng đơn đã in chưa ─────────────────
    try:
        df_orders = scan_pdf_for_orders(str(filepath))
        if not df_orders.empty:
            order_sns = df_orders["order_sn"].dropna().tolist()
            if order_sns:
                with get_session() as db:
                    existing = db.query(OrderPrint).filter(
                        OrderPrint.order_sn.in_(order_sns)
                    ).all()
                    if existing:
                        result["has_warnings"] = True
                        existing_map = {op.order_sn: op for op in existing}
                        for _, row in df_orders.iterrows():
                            op = existing_map.get(row["order_sn"])
                            if op:
                                result["order_warnings"].append({
                                    "order_sn":        op.order_sn,
                                    "shop_name":       op.shop_name,
                                    "platform":        op.platform,
                                    "delivery_method": op.delivery_method,
                                    "page_number":     int(row["page"]),
                                    "print_count":     op.print_count,
                                    "last_print_time": (
                                        op.last_print_time_utc.strftime("%Y-%m-%d %H:%M:%S")
                                        if op.last_print_time_utc else None
                                    ),
                                })
    except Exception as e:
        log_error("api_print_check.orders", e, {"filename": filename})

    return jsonify(result)


@app.route("/api/print", methods=["POST"])
def api_print():
    data           = request.get_json(force=True) or {}
    filename       = data.get("filename", "").strip()
    printer        = data.get("printer", "").strip()
    copies         = int(data.get("copies", 1))
    is_reprint     = bool(data.get("is_reprint", False))
    reprint_reason = data.get("reprint_reason", "").strip()
    client_ip      = request.remote_addr

    if not filename:
        return jsonify({"ok": False, "error": "Thiếu tên file."}), 400

    filepath = UPLOAD_FOLDER / filename
    if not filepath.exists():
        return jsonify({"ok": False, "error": f"File không tồn tại: {filename}"}), 404

    # ── Server-side validation: yêu cầu lý do nếu đã in trước đó ─
    try:
        with get_session() as db:
            prev_count = (
                db.query(PrintJob)
                .filter(PrintJob.filename == filename, PrintJob.status == "success")
                .count()
            )
        if prev_count > 0 and not is_reprint:
            return jsonify({
                "ok":                    False,
                "error":                 "File đã in trước đó. Vui lòng xác nhận lý do in lại.",
                "requires_reprint_reason": True,
            }), 409
    except Exception as e:
        log_error("api_print.check_prev", e)

    if is_reprint and not reprint_reason:
        return jsonify({"ok": False, "error": "Vui lòng nhập lý do in lại."}), 400

    # ── Quét PDF để lấy thông tin đơn hàng ───────────────────────
    orders_info = []
    try:
        df_orders = scan_pdf_for_orders(str(filepath))
        if not df_orders.empty:
            orders_info = df_orders.to_dict("records")
        else:
            log_warning(f"Không tìm thấy đơn hàng nào trong {filename}")
    except Exception as e:
        log_error("api_print.scan", e, {"filename": filename})
        # Vẫn tiếp tục in dù quét lỗi

    # ── Gửi lệnh in ──────────────────────────────────────────────
    try:
        sys.path.insert(0, str(BASE_DIR / "core"))
        from printing import print_pdf_printer

        success = True
        for _ in range(max(1, copies)):
            if not print_pdf_printer(str(filepath), printer or None):
                success = False
                break

        orders_summary = f"{len(orders_info)} đơn hàng" if orders_info else "Không xác định đơn hàng"
        now_utc        = _utcnow()
        status_str     = "success" if success else "error"

        # ── Ghi PrintJob vào DB ───────────────────────────────────
        try:
            with get_session() as db:
                db_job = PrintJob(
                    filename=filename,
                    printer_name=printer or "Default",
                    client_ip=client_ip,
                    copies=copies,
                    is_reprint=is_reprint,
                    reprint_reason=reprint_reason if is_reprint else None,
                    status=status_str,
                    print_time_utc=now_utc,
                )
                db.add(db_job)

                if success and orders_info:
                    for order in orders_info:
                        existing_op = db.query(OrderPrint).filter(
                            OrderPrint.order_sn == order["order_sn"]
                        ).first()
                        if existing_op:
                            existing_op.print_count         += 1
                            existing_op.last_print_time_utc  = now_utc
                            existing_op.filename             = filename
                        else:
                            db.add(OrderPrint(
                                filename=filename,
                                order_sn=order["order_sn"],
                                shop_name=order.get("shop_name"),
                                platform=order.get("platform", "unknown"),
                                delivery_method=order.get("delivery_method"),
                                delivery_method_raw=order.get("delivery_method_raw", ""),
                                page_number=order.get("page"),
                                print_count=1,
                                last_print_time_utc=now_utc,
                            ))
        except Exception as e:
            log_error("api_print.db", e)

        # Giữ jobs.json (backward compat)
        job = add_job(
            filename, printer or "Default", status_str,
            f"{copies} bản in - {orders_summary}" + (" [IN LẠI]" if is_reprint else "")
        )

        if success:
            log_info(f"In thành công: {filename} → {printer or 'Default'} x{copies} ({orders_summary})")
            return jsonify({"ok": True, "job": job, "orders": orders_info})
        else:
            msg = (
                "Gửi lệnh in thất bại. "
                "Gợi ý: Cài SumatraPDF (https://www.sumatrapdfreader.org) "
                "hoặc Adobe Acrobat Reader để in PDF tốt hơn."
            )
            return jsonify({"ok": False, "error": msg}), 500

    except Exception as e:
        log_error("api_print", e, {"filename": filename, "printer": printer})
        msg = str(e)
        add_job(filename, printer or "Default", "error", msg)
        return jsonify({"ok": False, "error": msg}), 500


# --- Lịch sử in (jobs.json - backward compat) --------------------------------

@app.route("/api/jobs")
def api_jobs():
    return jsonify({"jobs": load_jobs()})


# --- Lịch sử upload (DB) -----------------------------------------------------

@app.route("/api/files/history")
def api_files_history():
    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 20)))
    offset   = (page - 1) * per_page
    try:
        with get_session() as db:
            total = db.query(UploadedFile).count()
            rows  = (
                db.query(UploadedFile)
                .order_by(UploadedFile.upload_time_utc.desc())
                .offset(offset).limit(per_page).all()
            )
            files = [
                {
                    "id":            r.id,
                    "filename":      r.filename,
                    "original_name": r.original_name,
                    "upload_time":   r.upload_time_utc.strftime("%Y-%m-%d %H:%M:%S") if r.upload_time_utc else None,
                    "upload_ip":     r.upload_ip,
                    "file_size_kb":  r.file_size_kb,
                }
                for r in rows
            ]
        return jsonify({"ok": True, "files": files, "total": total, "page": page, "per_page": per_page})
    except Exception as e:
        log_error("api_files_history", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# --- Lịch sử in (DB) ---------------------------------------------------------

@app.route("/api/print-history")
def api_print_history():
    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 20)))
    offset   = (page - 1) * per_page
    try:
        with get_session() as db:
            total = db.query(PrintJob).count()
            rows  = (
                db.query(PrintJob)
                .order_by(PrintJob.print_time_utc.desc())
                .offset(offset).limit(per_page).all()
            )
            jobs = [
                {
                    "id":             r.id,
                    "filename":       r.filename,
                    "printer_name":   r.printer_name,
                    "client_ip":      r.client_ip,
                    "copies":         r.copies,
                    "is_reprint":     r.is_reprint,
                    "reprint_reason": r.reprint_reason,
                    "status":         r.status,
                    "print_time":     r.print_time_utc.strftime("%Y-%m-%d %H:%M:%S") if r.print_time_utc else None,
                }
                for r in rows
            ]
        return jsonify({"ok": True, "jobs": jobs, "total": total, "page": page, "per_page": per_page})
    except Exception as e:
        log_error("api_print_history", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# --- Lịch sử đơn hàng (DB) ---------------------------------------------------

@app.route("/api/orders/history")
def api_orders_history():
    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, int(request.args.get("per_page", 50)))
    order_sn = request.args.get("order_sn", "").strip()
    offset   = (page - 1) * per_page
    try:
        with get_session() as db:
            q = db.query(OrderPrint)
            if order_sn:
                q = q.filter(OrderPrint.order_sn.like(f"%{order_sn}%"))
            total = q.count()
            rows  = q.order_by(OrderPrint.last_print_time_utc.desc()).offset(offset).limit(per_page).all()
            orders = [
                {
                    "id":              r.id,
                    "filename":        r.filename,
                    "order_sn":        r.order_sn,
                    "shop_name":       r.shop_name,
                    "platform":        r.platform,
                    "delivery_method": r.delivery_method,
                    "delivery_method_raw": r.delivery_method_raw,
                    "page_number":     r.page_number,
                    "print_count":     r.print_count,
                    "last_print_time": (
                        r.last_print_time_utc.strftime("%Y-%m-%d %H:%M:%S")
                        if r.last_print_time_utc else None
                    ),
                }
                for r in rows
            ]
        return jsonify({"ok": True, "orders": orders, "total": total, "page": page, "per_page": per_page})
    except Exception as e:
        log_error("api_orders_history", e)
        return jsonify({"ok": False, "error": str(e)}), 500


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
