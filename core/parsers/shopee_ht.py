# -*- coding: utf-8 -*-
"""
core/parsers/shopee_ht.py
Parser cho Shopee Hỏa tốc.

Nhận dạng : có "Hỏa tốc" hoặc "Hỏa Tốc" trên trang
Platform  : shopee
Method code: SHT
"""

from __future__ import annotations

import re

from .base import BaseParser, PageResult
from .shopee_spx import _extract_shop_from_tu_den


class ShopeeSHTParser(BaseParser):

    _RE_DELIVERY = re.compile(r"Mã\s*[vV]ận\s*[đĐ]ơn\s*:\s*(\S+)", re.IGNORECASE)
    _RE_ORDER    = re.compile(r"Mã\s*[đd]ơn\s*hàng\s*:\s*(\S+)",    re.IGNORECASE)
    _RE_HOA_TOC  = re.compile(r"Hỏa\s*[tT]ốc", re.IGNORECASE)

    def can_handle(self, full_text: str, words: list) -> bool:
        # Tìm vị trí của "Hỏa Tốc" và "Mã đơn hàng"
        m_hoa_toc = self._RE_HOA_TOC.search(full_text)
        m_order = self._RE_ORDER.search(full_text)
        
        # Kiểm tra "Hỏa Tốc" có đứng trước "Mã đơn hàng" không
        if m_hoa_toc and m_order:
            return m_hoa_toc.start() < m_order.start()
        return False

    def parse(
        self, page_number: int, full_text: str, words: list, page
    ) -> PageResult:
        m_order  = self._RE_ORDER.search(full_text)
        order_sn = m_order.group(1) if m_order else None
        shop_name = _extract_shop_from_tu_den(words)

        return PageResult(
            page_number=page_number,
            order_sn=order_sn,
            shop_name=shop_name,
            platform="shopee",
            delivery_method="SHT",
            delivery_method_raw="Shopee Hỏa tốc",
        )
