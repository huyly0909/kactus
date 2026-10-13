#!/usr/bin/env python3
"""Tests for the SjcGoldSource implementation (sjc.com.vn)."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from kactus_data.sources.gold.sjc import (
    HISTORY_WINDOW_DAYS,
    SUPPORTED_CODES,
    SjcGoldSource,
    history_windows,
)

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


# 2009-01-01 08:00 and 12:00 in VN (UTC+7), as epoch-ms /Date()/ stamps.
_D1_MORNING_MS = 1230771600000
_D1_NOON_MS = 1230786000000
_D2_MS = 1230858000000  # 2009-01-02 08:00 VN


def _tick(ms: int, buy, sell) -> dict:
    return {"GroupDate": f"/Date({ms})/", "BuyValue": buy, "SellValue": sell}


class TestSjcGoldHistory:
    def test_windows_are_disjoint_and_cover_range(self):
        wins = list(history_windows(date(2009, 1, 1), date(2009, 4, 15)))
        assert wins[0][0] == date(2009, 1, 1)
        assert wins[-1][1] == date(2009, 4, 15)
        # ≤ window size, and each window starts the day after the previous ends.
        assert all((b - a).days < HISTORY_WINDOW_DAYS for a, b in wins)
        for (_, prev_end), (nxt_start, _) in zip(wins, wins[1:]):
            assert nxt_start == date.fromordinal(prev_end.toordinal() + 1)

    def test_single_day_window(self):
        assert list(history_windows(date(2020, 5, 1), date(2020, 5, 1))) == [
            (date(2020, 5, 1), date(2020, 5, 1))
        ]

    def test_history_reduces_ticks_to_last_of_day(self):
        """Multiple ticks per day collapse to one row — the latest tick wins."""
        ticks = [
            _tick(_D1_MORNING_MS, 1_000_000, 1_010_000),
            _tick(_D1_NOON_MS, 1_002_000, 1_012_000),  # later same day → wins
            _tick(_D2_MS, 1_003_000, 1_013_000),
        ]
        src = SjcGoldSource()
        src._fetch_history = lambda session, frm, to: ticks
        rows = src.history(date(2009, 1, 1), date(2009, 1, 2))

        assert [r["date"] for r in rows] == [date(2009, 1, 1), date(2009, 1, 2)]
        assert rows[0]["buy_price"] == Decimal("1002000.0000")  # noon, not morning
        assert isinstance(rows[0]["buy_price"], Decimal)  # never float (VND ~1e8)

    def test_history_skips_zero_and_undated_ticks(self):
        ticks = [
            _tick(_D1_NOON_MS, 1_002_000, 1_012_000),
            _tick(_D2_MS, 0, 0),  # both-zero sentinel → skipped
            {"GroupDate": "bad", "BuyValue": 5, "SellValue": 6},  # no date → skipped
        ]
        src = SjcGoldSource()
        src._fetch_history = lambda session, frm, to: ticks
        rows = src.history(date(2009, 1, 1), date(2009, 1, 2))
        assert [r["date"] for r in rows] == [date(2009, 1, 1)]

    @patch("kactus_data.sources.gold.sjc.curl_requests.Session")
    def test_history_cloudflare_block_degrades(self, mock_session_cls):
        session = mock_session_cls.return_value
        session.post.side_effect = RuntimeError("403 challenge")
        assert SjcGoldSource().history(date(2009, 1, 1), date(2009, 1, 5)) == []
