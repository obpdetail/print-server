# -*- coding: utf-8 -*-
"""
core/parsers/shopee_spx.py
Parser cho Shopee SPX (SPX Instant + SPX Express).

Nhận dạng : delivery_id bắt đầu bằng "SPX"
Platform  : shopee
Method code: SPX
Raw text   : "SPX Instant" | "SPX Express" | "SPX" (tùy nhận dạng được hay không)
"""

from __future__ import annotations

import re

from .base import BaseParser, PageResult


class ShopeeSPXParser(BaseParser):

    _RE_DELIVERY = re.compile(r"Mã\s*[vV]ận\s*[đĐ]ơn\s*:\s*(\S+)", re.IGNORECASE)
    _RE_ORDER    = re.compile(r"Mã\s*[đd]ơn\s*hàng\s*:\s*(\S+)",    re.IGNORECASE)

    def can_handle(self, full_text: str, words: list) -> bool:
        m = self._RE_DELIVERY.search(full_text)
        return bool(m and m.group(1).upper().startswith("SPX"))

    def parse(
        self, page_number: int, full_text: str, words: list, page
    ) -> PageResult:
        # ── Mã đơn ──────────────────────────────────────────────
        m_order  = self._RE_ORDER.search(full_text)
        order_sn = m_order.group(1) if m_order else None

        # ── Tên shop ─────────────────────────────────────────────
        shop_name = _extract_shop_from_tu_den(words)

        # ── Phân biệt SPX Instant vs SPX Express ─────────────────
        # Tìm từ khóa đặc trưng trên trang để phân biệt
        txt_upper = full_text.upper()
        if "INSTANT" in txt_upper or "TỨC THÌ" in txt_upper:
            raw = "SPX Instant"
        elif "NHANH" in txt_upper or "EXPRESS" in txt_upper:
            raw = "SPX Express"
        else:
            raw = "SPX"

        return PageResult(
            page_number=page_number,
            order_sn=order_sn,
            shop_name=shop_name,
            platform="shopee",
            delivery_method="SPX",
            delivery_method_raw=raw,
        )


# ── Shared helper (dùng cho SPX + GHN + VNP + HT) ────────────

def _extract_shop_from_tu_den(words: list) -> str:
    """
    Lấy tên shop từ dòng ngay dưới "Từ:" ở bên trái cột "Đến:".
    Dùng cho layout chuẩn Shopee (SPX, GHN, VNP, HT).
    """
    den_x0     = None
    tu_y1      = None
    shop_words = []
    found_line = False

    for w in words:
        if "Đến:" in w["text"]:
            den_x0 = w["x0"]
            break

    for w in words:
        if "Từ:" in w["text"]:
            tu_y1 = w["bottom"]
            break

    if den_x0 is not None and tu_y1 is not None:
        for w in words:
            if tu_y1 < w["top"] < tu_y1 + 20:
                if w["x0"] < den_x0:
                    shop_words.append(w["text"])
                    found_line = True
                elif found_line:
                    break  # dừng khi sang cột "Đến:"

    return " ".join(shop_words).strip() or "UNKNOWN_SHOP"
