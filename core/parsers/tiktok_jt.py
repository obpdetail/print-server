# -*- coding: utf-8 -*-
"""
core/parsers/tiktok_jt.py
Parser cho TikTok Shop – J&T Express.

Nhận dạng : có "Package ID:" trên trang (thay vì "Mã vận đơn:")
Platform  : tiktok
Method code: JT
"""

from __future__ import annotations

import re

from .base import BaseParser, PageResult


class TikTokJTParser(BaseParser):

    _RE_PACKAGE  = re.compile(r"Package\s*ID\s*:\s*(\S+)",  re.IGNORECASE)
    _RE_ORDER    = re.compile(r"Order\s*ID\s*:\s*(\S+)",     re.IGNORECASE)
    _RE_SHOP     = re.compile(
        r"Người\s+gửi\s*[\n\r\s]*([^\n\r]+?)"
        r"(?=\n|\r|Căn|Số|Phường|Xã|Quận|Huyện|Thành\s*phố|[0-9])",
        re.IGNORECASE,
    )

    def can_handle(self, full_text: str, words: list) -> bool:
        return bool(self._RE_PACKAGE.search(full_text))

    def parse(
        self, page_number: int, full_text: str, words: list, page
    ) -> PageResult:
        # ── Mã đơn ──────────────────────────────────────────────
        m_order  = self._RE_ORDER.search(full_text)
        order_sn = m_order.group(1) if m_order else None

        # ── Tên shop ─────────────────────────────────────────────
        shop_name = self._extract_shop_name(full_text)

        return PageResult(
            page_number=page_number,
            order_sn=order_sn,
            shop_name=shop_name,
            platform="tiktok",
            delivery_method="JT",
            delivery_method_raw="J&T Express",
        )

    def _extract_shop_name(self, full_text: str) -> str:
        m = self._RE_SHOP.search(full_text)
        if not m:
            return "UNKNOWN_SHOP"
        raw    = m.group(1).strip()
        parts  = raw.split()
        result = []
        for part in parts:
            if not part:
                continue
            digit_ratio = sum(c.isdigit() for c in part) / len(part)
            if digit_ratio >= 0.5:
                break   # dừng khi gặp chuỗi có nhiều số (địa chỉ)
            result.append(part)
        return " ".join(result) if result else raw
