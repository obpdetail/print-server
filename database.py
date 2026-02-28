# -*- coding: utf-8 -*-
"""
database.py — SQLAlchemy ORM models + session helpers (MySQL)

Tables:
    uploaded_files  — lịch sử upload
    print_jobs      — lịch sử lệnh in
    order_prints    — lịch sử đơn hàng đã in (tích lũy print_count theo order_sn)
"""

from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer, String, Text, create_engine, text
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import DATABASE_URL, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


# ── Engine & Session ──────────────────────────────────────────

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


# ── Helpers ───────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Trả về datetime UTC không có tzinfo (để lưu vào MySQL DATETIME)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Models ────────────────────────────────────────────────────

class UploadedFile(Base):
    """Quản lý các file PDF đã upload lên server."""
    __tablename__ = "uploaded_files"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    filename        = Column(String(255), nullable=False, unique=True, index=True)
    # ^ tên duy nhất trên disk (có timestamp prefix)
    original_name   = Column(String(255), nullable=False)
    # ^ tên file gốc trước khi thêm timestamp
    upload_time_utc = Column(DateTime, nullable=False, default=_utcnow)
    upload_ip       = Column(String(45), nullable=True)   # IPv4 hoặc IPv6
    file_size_kb    = Column(Integer, nullable=True)
    created_date    = Column(DateTime, nullable=False, default=_utcnow)
    updated_date    = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class PrintJob(Base):
    """Lịch sử các lệnh in."""
    __tablename__ = "print_jobs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    filename        = Column(String(255), nullable=False, index=True)
    printer_name    = Column(String(255), nullable=True)
    client_ip       = Column(String(45),  nullable=True)  # IP máy gửi lệnh in
    copies          = Column(Integer, nullable=False, default=1)
    is_reprint      = Column(Boolean, nullable=False, default=False)
    reprint_reason  = Column(Text, nullable=True)
    status          = Column(String(20), nullable=False, default="success")
    # ^ "success" | "error"
    print_time_utc  = Column(DateTime, nullable=False, default=_utcnow)
    created_date    = Column(DateTime, nullable=False, default=_utcnow)
    updated_date    = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class OrderPrint(Base):
    """
    Thông tin đơn hàng đã in. Mỗi order_sn có đúng 1 bản ghi.
    print_count tích lũy toàn bộ lịch sử — tăng +1 mỗi lần in.
    """
    __tablename__ = "order_prints"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    filename            = Column(String(255), nullable=False, index=True)
    # ^ file gần nhất chứa đơn này
    order_sn            = Column(String(100), nullable=False)
    shop_name           = Column(String(255), nullable=True)
    platform            = Column(String(50),  nullable=True)
    # ^ "shopee" | "tiktok" | "lazada" | "unknown"
    delivery_method     = Column(String(50),  nullable=True)
    # ^ code chuẩn hóa: "SPX" | "GHN" | "JT" | "VTP" | "VNP" | "HT" | ...
    delivery_method_raw = Column(String(100), nullable=True)
    # ^ text gốc từ PDF (để debug / phân biệt SPX Instant vs SPX Express)
    page_number         = Column(Integer, nullable=True)
    print_count         = Column(Integer, nullable=False, default=1)
    # ^ tổng số lần đơn này được in (tích lũy)
    last_print_time_utc = Column(DateTime, nullable=True)
    created_date        = Column(DateTime, nullable=False, default=_utcnow)
    updated_date        = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_order_prints_order_sn", "order_sn"),
    )


# ── Session context manager ───────────────────────────────────

@contextmanager
def get_session():
    """
    Context manager trả về Session. Tự commit khi thành công,
    rollback khi có exception, luôn đóng session sau khi dùng.

    Cách dùng:
        with get_session() as db:
            db.add(SomeModel(...))
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Init ──────────────────────────────────────────────────────

def init_db():
    """
    Tạo database (nếu chưa tồn tại) và tất cả các bảng.
    Gọi một lần khi khởi động ứng dụng.
    """
    # Tạo database nếu chưa có
    root_url = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}?charset=utf8mb4"
    )
    tmp_engine = create_engine(root_url, pool_pre_ping=True)
    with tmp_engine.connect() as conn:
        conn.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
        conn.commit()
    tmp_engine.dispose()

    # Tạo tất cả bảng
    Base.metadata.create_all(bind=engine)
