# -*- coding: utf-8 -*-
"""
core/parsers/__init__.py
Dispatcher: chọn parser phù hợp cho từng trang PDF.

Để thêm ĐVVC / nền tảng mới:
  1. Tạo file parser mới trong thư mục này
  2. Import class vào đây
  3. Thêm instance vào PARSERS theo đúng thứ tự ưu tiên
     (parser đầu tiên match sẽ được dùng)
"""

from __future__ import annotations

from .base       import PageResult
from .shopee_spx import ShopeeSPXParser
from .shopee_ghn import ShopeeGHNParser
from .tiktok_jt  import TikTokJTParser

# ── Thứ tự ưu tiên ───────────────────────────────────────────
# TikTok/J&T phải đứng trước Shopee vì nó dùng "Package ID"
# thay vì "Mã vận đơn" — không bị nhầm với SPX / GHN.
PARSERS = [
    TikTokJTParser(),
    ShopeeSPXParser(),
    ShopeeGHNParser(),
    # TODO: thêm ShopeeVTPParser(), ShopeVNPParser(), LazadaNinjaParser() ...
]


def dispatch_page(
    page_number: int,
    full_text: str,
    words: list,
    page,
) -> PageResult | None:
    """
    Thử từng parser trong PARSERS theo thứ tự.
    Trả về PageResult nếu có parser nhận dạng được,
    None nếu không có parser nào khớp.
    """
    for parser in PARSERS:
        if parser.can_handle(full_text, words):
            return parser.parse(page_number, full_text, words, page)
    return None
