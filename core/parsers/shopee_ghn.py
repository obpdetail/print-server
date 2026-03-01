# -*- coding: utf-8 -*-
"""
core/parsers/shopee_ghn.py
Parser cho Shopee Giao Hàng Nhanh (GHN).

Nhận dạng : delivery_id bắt đầu bằng "GY"
Platform  : shopee
Method code: GHN
"""

from __future__ import annotations

import re

from .base import BaseParser, PageResult
from .shopee_spx import _extract_shop_from_tu_den


class ShopeeGHNParser(BaseParser):

    _RE_DELIVERY = re.compile(r"Mã\s*[vV]ận\s*[đĐ]ơn\s*:\s*(\S+)", re.IGNORECASE)
    _RE_ORDER    = re.compile(r"Mã\s*[đd]ơn\s*hàng\s*:\s*(\S+)",    re.IGNORECASE)

    def can_handle(self, full_text: str, words: list) -> bool:
        m = self._RE_DELIVERY.search(full_text)
        return bool(m and m.group(1).upper().startswith("GY"))

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
            delivery_method="GHN",
            delivery_method_raw="Giao Hàng Nhanh",
        )
