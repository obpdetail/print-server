# -*- coding: utf-8 -*-
"""
core/parsers/spx_offplatform.py
Parser cho đơn SPX ngoại sàn (phiếu ảnh / ĐƠN NGOÀI SÀN).

Nhận dạng : có "ĐƠN NGOÀI SÀN" / "NGOAI SAN" hoặc mã vận đơn SPXVN…
Platform  : external
Method code: SPX
Raw text   : SPX Ngoại sàn
"""

from __future__ import annotations

import re
import unicodedata

from .base import BaseParser, PageResult


def _strip_accents(s: str) -> str:
    nk = unicodedata.normalize("NFD", s)
    return "".join(c for c in nk if unicodedata.category(c) != "Mn")


class SPXOffPlatformParser(BaseParser):
    """Đơn SPX ngoài sàn Shopee (thường là PDF scan/ảnh)."""

    _RE_ORDER = re.compile(
        r"M[aã]\s*[đd]ơn\s*h[aà]ng\s*:\s*([A-Z0-9]+)",
        re.IGNORECASE,
    )
    _RE_ORDER_ASCII = re.compile(
        r"Ma\s*don\s*hang\s*:\s*([A-Z0-9]+)",
        re.IGNORECASE,
    )
    _RE_WAYBILL = re.compile(r"\b(SPXVN[0-9O]{8,})\b", re.IGNORECASE)
    _RE_SHOP = re.compile(
        r"T[ừưu]\s*:\s*([^\n\r(]+)",
        re.IGNORECASE,
    )
    _RE_SHOP_ASCII = re.compile(
        r"Tu\s*:\s*([^\n\r(]+)",
        re.IGNORECASE,
    )

    def can_handle(self, full_text: str, words: list) -> bool:
        if not (full_text or "").strip():
            return False
        norm = _strip_accents(full_text).upper()
        has_off = "NGOAI SAN" in norm or "DON NGOAI" in norm
        has_spxvn = bool(self._RE_WAYBILL.search(full_text))
        has_order = bool(
            self._RE_ORDER.search(full_text) or self._RE_ORDER_ASCII.search(norm)
        )
        # Phiếu ngoại sàn chuẩn, hoặc SPXVN + mã đơn hàng (OCR)
        return has_off or (has_spxvn and has_order)

    def parse(
        self, page_number: int, full_text: str, words: list, page
    ) -> PageResult:
        m_order = self._RE_ORDER.search(full_text)
        if not m_order:
            m_order = self._RE_ORDER_ASCII.search(_strip_accents(full_text))
        order_sn = m_order.group(1).strip() if m_order else None

        shop_name = self._extract_shop(full_text)

        return PageResult(
            page_number=page_number,
            order_sn=order_sn,
            shop_name=shop_name,
            platform="external",
            delivery_method="SPX",
            delivery_method_raw="SPX Ngoại sàn",
        )

    def _extract_shop(self, full_text: str) -> str:
        m = self._RE_SHOP.search(full_text)
        if not m:
            m = self._RE_SHOP_ASCII.search(_strip_accents(full_text))
        if not m:
            return "UNKNOWN_SHOP"
        raw = m.group(1).strip()
        # Bỏ đuôi số ĐT nếu dính
        raw = re.split(r"\s*\(", raw, maxsplit=1)[0].strip()
        return raw or "UNKNOWN_SHOP"
