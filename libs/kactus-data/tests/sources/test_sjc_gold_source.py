#!/usr/bin/env python3
"""Tests for the SjcGoldSource implementation (sjc.com.vn)."""

from unittest.mock import MagicMock, patch

from kactus_data.sources.gold.sjc import SUPPORTED_CODES, SjcGoldSource

# Trimmed shape of the real PriceService.ashx payload.
BOARD = [
    {
        "TypeName": "Vàng SJC 1L, 10L, 1KG",
        "BranchName": "Hồ Chí Minh",
        "BuyValue": 134500000.0,
        "SellValue": 139500000.0,
    },
    {
        "TypeName": "Vàng SJC 1L, 10L, 1KG",
        "BranchName": "Miền Bắc",
        "BuyValue": 135500000.0,
        "SellValue": 140500000.0,
    },
    {
        "TypeName": "Vàng nhẫn SJC 99,99% 1 chỉ, 2 chỉ, 5 chỉ",
        "BranchName": "Hồ Chí Minh",
        "BuyValue": 133500000.0,
        "SellValue": 138500000.0,
    },
]


class TestSjcGoldSource:
    def test_supported_codes(self):
        assert SUPPORTED_CODES == {"SJC", "999"}

    def test_quote_uses_reference_branch(self):
        """HCM is the reference branch — Miền Bắc must not win."""
        quote = SjcGoldSource().quote("SJC", board=BOARD)
        assert quote["buy_price"] == 134500000.0
        assert quote["sell_price"] == 139500000.0

    def test_quote_maps_999_to_sjc_ring(self):
        quote = SjcGoldSource().quote("999", board=BOARD)
        assert quote["buy_price"] == 133500000.0

    def test_quote_is_case_insensitive(self):
        assert SjcGoldSource().quote("sjc", board=BOARD) is not None

    def test_quote_unknown_code_returns_none(self):
        """SJC does not publish other companies' products."""
        assert SjcGoldSource().quote("DOJI", board=BOARD) is None
        assert SjcGoldSource().quote("PNJ", board=BOARD) is None

    def test_quote_missing_type_returns_none(self):
        assert SjcGoldSource().quote("SJC", board=[]) is None

    @patch("kactus_data.sources.gold.sjc.curl_requests.post")
    def test_fetch_board_success(self, mock_post):
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={"success": True, "data": BOARD})
        )
        assert len(SjcGoldSource().fetch_board()) == 3

    @patch("kactus_data.sources.gold.sjc.curl_requests.post")
    def test_fetch_board_cloudflare_block_degrades(self, mock_post):
        """A Cloudflare 403 must degrade to [], never raise — the crawl falls back."""
        mock_post.side_effect = RuntimeError("403 challenge")
        assert SjcGoldSource().fetch_board() == []

    @patch("kactus_data.sources.gold.sjc.curl_requests.post")
    def test_fetch_board_unsuccessful_payload(self, mock_post):
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={"success": False})
        )
        assert SjcGoldSource().fetch_board() == []
