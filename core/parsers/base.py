# -*- coding: utf-8 -*-
"""
core/parsers/base.py
Abstract base class và PageResult dataclass dùng cho toàn bộ parser.

Để thêm ĐVVC / nền tảng mới:
  1. Tạo file mới trong core/parsers/  (vd: lazada_ninja.py)
  2. Subclass BaseParser, implement can_handle() + parse()
  3. Đăng ký instance vào PARSERS list trong core/parsers/__init__.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PageResult:
    """Kết quả parse 1 trang PDF."""
    page_number:         int
    order_sn:            Optional[str]
    shop_name:           Optional[str]
    platform:            str   # "shopee" | "tiktok" | "lazada" | "unknown"
    delivery_method:     str   # code chuẩn hóa: "SPX" | "GHN" | "JT" | "VTP" | ...
    delivery_method_raw: str = field(default="")
    # ^ text gốc để debug / phân biệt chi tiết (SPX Instant vs SPX Express...)


class BaseParser(ABC):
    """
    Parser cơ sở. Mỗi subclass đảm nhận 1 loại vận đơn cụ thể.

    Vòng đời:
        dispatcher gọi can_handle() cho mỗi trang
        → nếu True, gọi parse() để lấy PageResult
        → nếu False, thử parser tiếp theo trong danh sách PARSERS
    """

    @abstractmethod
    def can_handle(self, full_text: str, words: list) -> bool:
        """
        Kiểm tra nhanh xem trang này có thuộc loại ĐVVC này không.
        Chỉ dùng regex nhẹ / check từ khóa đặc trưng.
        """
        ...

    @abstractmethod
    def parse(
        self,
        page_number: int,
        full_text: str,
        words: list,
        page,              # pdfplumber Page object
    ) -> PageResult:
        """
        Parse toàn bộ thông tin từ trang và trả về PageResult.
        `page` là pdfplumber Page — dùng khi cần crop bbox hoặc extract_words.
        """
        ...
