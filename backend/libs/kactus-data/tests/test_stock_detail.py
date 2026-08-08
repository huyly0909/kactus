"""Stock-detail read models: daily snapshot, analytics, and the two bug fixes.

Every case here encodes a real defect found by comparing stored rows against
the exchange, so the numbers are the ones actually observed for FPT on
2026-07-27 rather than invented fixtures.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from kactus_common.config import clear_settings, register_settings
from kactus_data.config import DataSettings
from kactus_data.market import analytics
from kactus_data.sources.finance.vnstock import _period_pivot
from kactus_data.sources.stock.market import (
    ACC_VALUE_UNIT_VND,
    StockMarketSource,
    _depth_sum,
    _pick,
    daily_snapshot,
)

# The shape VCI actually returns, flattened — abbreviated to the fields the
# snapshot reads, with the real FPT 2026-07-27 values.
FPT_BOARD_RAW = {
    "listing_symbol": "FPT",
    "listing_trading_date": "2026-07-27",
    "listing_ref_price": 62900,
    "listing_ceiling": 67300,
    "listing_floor": 58500,
    # The trap: the ATO price sits next to the real match price and matches a
    # substring search for "match_price" first.
    "match_match_price_ato": 63100,
    "match_match_price_atc": 62200,
    "match_match_price": 62200,
    "match_reference_price": 62900,
    "match_accumulated_volume": 4449500,
    "match_accumulated_value": 279654.55,  # millions of VND
    "match_open_price": 63100,
    "match_highest": 63700,
    "match_lowest": 62200,
    "match_foreign_buy_volume": 835647,
    "match_foreign_sell_volume": 836200,
    "match_foreign_buy_value": 52667461000,  # absolute VND
    "match_foreign_sell_value": 52553210000,
    "match_current_room": 374545907,
    "match_total_room": 834718489,
    # Order counts read 0 during the ATC window.
    "match_total_buy_orders": 0,
    "match_total_sell_orders": 0,
    "bid_ask_bid_1_volume": 45000,
    "bid_ask_bid_2_volume": 104600,
    "bid_ask_bid_3_volume": 218100,
    "bid_ask_ask_1_volume": 44700,
    "bid_ask_ask_2_volume": 11800,
    "bid_ask_ask_3_volume": 1000,
}


@pytest.fixture
def settings():
    """Source methods pace themselves off the vnstock budget, which reads settings."""
    register_settings(DataSettings())
    try:
        yield
    finally:
        clear_settings()


def _board_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "FPT",
                "match_price": 62200.0,
                "ref_price": 62900.0,
                "accumulated_volume": 4449500.0,
                "raw_json": json.dumps(FPT_BOARD_RAW),
            }
        ]
    )


# --------------------------------------------------------------------------- #
# _pick — the ATO / thumbnail near-miss
# --------------------------------------------------------------------------- #
def test_pick_substring_would_return_the_ato_price_without_exclusion():
    """Documents the defect: an unguarded substring search picks up ATO."""
    assert _pick(FPT_BOARD_RAW, "match_price") == 63100  # the auction price


def test_pick_excludes_auction_fields():
    assert _pick(FPT_BOARD_RAW, "match_price", exclude=("_ato", "_atc")) == 62200


def test_price_board_stores_the_close_not_the_auction_price(settings):
    class Fake(StockMarketSource):
        def _raw_price_board(self, codes):
            return pd.DataFrame([FPT_BOARD_RAW])

    df = Fake(source="VCI").price_board(["FPT"])
    assert len(df) == 1
    assert df.iloc[0]["match_price"] == 62200
    assert df.iloc[0]["ref_price"] == 62900
    assert df.iloc[0]["accumulated_volume"] == 4449500


def test_news_url_is_null_rather_than_the_thumbnail(settings):
    """VCI leaves news_source_link null; the image URL must not stand in."""

    class Fake(StockMarketSource):
        def _raw_news(self, code):
            return pd.DataFrame(
                [
                    {
                        "id": "n1",
                        "news_title": "FPT: something",
                        "public_date": "2026-07-21",
                        "news_source_link": None,
                        "news_image_url": "https://cdn.example/thumb.png",
                    }
                ]
            )

    df = Fake(source="VCI").news(["FPT"])
    assert df.iloc[0]["url"] is None


# --------------------------------------------------------------------------- #
# daily_snapshot
# --------------------------------------------------------------------------- #
def test_daily_snapshot_matches_the_exchange():
    row = daily_snapshot(_board_frame(), source="VCI").iloc[0]

    assert row["trade_date"] == "2026-07-27"  # from the board, not the clock
    assert row["close_price"] == 62200
    assert row["change"] == -700
    assert row["change_pct"] == pytest.approx(-1.11, abs=0.01)
    assert row["volume"] == 4449500
    # Millions → absolute VND: 279.65bn.
    assert row["value_vnd"] == pytest.approx(279654.55 * ACC_VALUE_UNIT_VND)
    # Foreign values are already absolute VND and must NOT be scaled.
    assert row["foreign_buy_value"] == pytest.approx(52.667461e9)
    assert row["foreign_sell_value"] == pytest.approx(52.553210e9)
    assert row["foreign_net_value"] == pytest.approx(52.667461e9 - 52.553210e9)


def test_daily_snapshot_sums_every_depth_level():
    row = daily_snapshot(_board_frame(), source="VCI").iloc[0]
    assert row["remain_bid"] == 45000 + 104600 + 218100
    assert row["remain_ask"] == 44700 + 11800 + 1000
    # Level 1 alone would be an order of magnitude smaller.
    assert row["remain_bid"] != FPT_BOARD_RAW["bid_ask_bid_1_volume"]


def test_daily_snapshot_leaves_average_size_null_when_orders_unpublished():
    """Zero orders during ATC means "not published", not "no orders"."""
    row = daily_snapshot(_board_frame(), source="VCI").iloc[0]
    assert row["avg_buy_size"] is None
    assert row["avg_sell_size"] is None


def test_daily_snapshot_falls_back_to_today_without_a_session_date():
    raw = {k: v for k, v in FPT_BOARD_RAW.items() if k != "listing_trading_date"}
    board = pd.DataFrame([{"symbol": "FPT", "raw_json": json.dumps(raw)}])
    assert daily_snapshot(board, source="VCI").iloc[0]["trade_date"]


def test_daily_snapshot_of_an_empty_board_keeps_table_columns():
    out = daily_snapshot(pd.DataFrame(), source="VCI")
    assert out.empty
    assert "foreign_net_value" in out.columns


def test_depth_sum_returns_none_when_no_level_published():
    assert _depth_sum({}, "bid") is None


# --------------------------------------------------------------------------- #
# finance pivot — transposed statements collapsed onto one primary key
# --------------------------------------------------------------------------- #
def test_period_pivot_splits_transposed_statement_into_periods():
    raw = pd.DataFrame(
        {
            "item_id": ["net_sales", "net_profit_loss_after_tax"],
            "2025-Q3": [17205e9, 2902e9],
            "2025-Q4": [20225e9, 2995e9],
        }
    )
    out = _period_pivot(raw)
    assert [(label, y, q) for label, y, q, _ in out] == [
        ("2025-Q3", 2025, 3),
        ("2025-Q4", 2025, 4),
    ]
    assert out[1][3]["net_sales"] == 20225e9


def test_period_pivot_handles_annual_headers():
    raw = pd.DataFrame({"item_id": ["equity"], "2025": [40122e9]})
    label, year, quarter, metrics = _period_pivot(raw)[0]
    assert (label, year, quarter) == ("2025", 2025, 0)
    assert metrics["equity"] == 40122e9


def test_period_pivot_returns_empty_for_a_tidy_frame():
    """No period-shaped headers → caller keeps one-row-per-record."""
    assert _period_pivot(pd.DataFrame({"year": [2025], "quarter": [3]})) == []


# --------------------------------------------------------------------------- #
# analytics — technical
# --------------------------------------------------------------------------- #
def _candles(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1_000_000.0] * len(closes),
        },
        index=idx,
    )


def test_technical_gauge_reads_strong_sell_on_a_sustained_decline():
    df = _candles([100 - i * 0.2 for i in range(260)])
    out = analytics.technical_gauge(df)
    assert out["label"] == "STRONG_SELL"
    assert out["score"] < -0.5
    assert out["counts"]["sell"] > out["counts"]["buy"]


def test_technical_gauge_reads_strong_buy_on_a_sustained_rally():
    df = _candles([100 + i * 0.2 for i in range(260)])
    out = analytics.technical_gauge(df)
    assert out["label"] == "STRONG_BUY"
    assert out["score"] > 0.5


def test_technical_gauge_reports_no_data_below_the_warmup_threshold():
    out = analytics.technical_gauge(_candles([100.0] * 5))
    assert out["label"] == "NO_DATA"
    assert out["score"] is None
    assert out["signals"] == []


def test_technical_gauge_omits_averages_without_enough_history():
    """A 200-day average over 60 bars is no reading, not a neutral one."""
    out = analytics.technical_gauge(_candles([100 + i * 0.1 for i in range(60)]))
    names = {s["name"] for s in out["signals"]}
    assert "SMA(50)" in names
    assert "SMA(200)" not in names


@pytest.mark.parametrize("interval", ["1D", "1W", "1M"])
def test_technical_gauge_supports_every_rollup(interval):
    df = _candles([100 + i * 0.2 for i in range(400)])
    out = analytics.technical_gauge(df, interval)
    assert out["interval"] == interval
    assert out["bars"] > 0


def test_weekly_rollup_has_fewer_bars_than_daily():
    df = _candles([100.0 + i for i in range(140)])
    assert len(analytics.resample_ohlcv(df, "1W")) < len(df)


# --------------------------------------------------------------------------- #
# analytics — fundamental
# --------------------------------------------------------------------------- #
def _peers(n: int = 6) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "roe": [0.05 * (i + 1) for i in range(n)],
            "roa": [0.02 * (i + 1) for i in range(n)],
            "roic": [0.03 * (i + 1) for i in range(n)],
            "net_margin": [0.04 * (i + 1) for i in range(n)],
            "gross_margin": [0.10 * (i + 1) for i in range(n)],
            "ebit_margin": [0.05 * (i + 1) for i in range(n)],
            "current_ratio": [1.0 + i for i in range(n)],
            "quick_ratio": [0.8 + i for i in range(n)],
            "cash_ratio": [0.2 + i for i in range(n)],
            "pe_ratio": [30.0 - i for i in range(n)],
            "pb_ratio": [6.0 - 0.5 * i for i in range(n)],
            "ps_ratio": [5.0 - 0.4 * i for i in range(n)],
            "dividend_yield": [0.01 * (i + 1) for i in range(n)],
            "price_to_cash_flow": [20.0 - i for i in range(n)],
        },
        index=[f"S{i}" for i in range(n)],
    )


def test_fundamental_radar_ranks_the_best_peer_top():
    out = analytics.fundamental_radar(_peers(), "S5")
    assert out["available"] is True
    profitability = next(a for a in out["axes"] if a["axis"] == "Profitability")
    assert profitability["score"] == pytest.approx(10.0)
    assert out["grade"] in {"A", "B"}


def test_fundamental_radar_reports_every_axis_with_the_industry_baseline():
    out = analytics.fundamental_radar(_peers(), "S2")
    assert [a["axis"] for a in out["axes"]] == list(analytics.AXIS_ORDER)
    scored = [a for a in out["axes"] if a["score"] is not None]
    assert scored and all(a["industry"] == 5.0 for a in scored)


def test_fundamental_radar_needs_a_minimum_peer_count():
    out = analytics.fundamental_radar(_peers(2), "S0")
    assert out["available"] is False
    assert "peers" in out["reason"]


def test_fundamental_radar_reports_unknown_symbol():
    out = analytics.fundamental_radar(_peers(), "NOPE")
    assert out["available"] is False


def test_fundamental_radar_skips_all_zero_columns():
    """vnstock writes 0.0, not null, for ratios that do not apply."""
    peers = _peers()
    peers["roe"] = 0.0
    out = analytics.fundamental_radar(peers, "S5")
    profitability = next(a for a in out["axes"] if a["axis"] == "Profitability")
    assert "roe" not in {m["metric"] for m in profitability["metrics"]}


def test_fundamental_radar_ignores_negative_inverted_metrics():
    """A negative P/E is loss-making, not cheap — it must not rank best."""
    peers = _peers()
    peers.loc["S0", "pe_ratio"] = -5.0
    out = analytics.fundamental_radar(peers, "S0")
    valuation = next(a for a in out["axes"] if a["axis"] == "Valuation")
    assert "pe_ratio" not in {m["metric"] for m in valuation["metrics"]}


def test_fundamental_radar_uses_the_banking_metric_map():
    peers = pd.DataFrame(
        {
            "roe": [0.05 * (i + 1) for i in range(6)],
            "roa": [0.01 * (i + 1) for i in range(6)],
            "net_interest_margin": [0.02 * (i + 1) for i in range(6)],
            "cost_to_income_ratio": [0.6 - 0.05 * i for i in range(6)],
            "non_interest_income": [1e9 * (i + 1) for i in range(6)],
            "npl": [0.05 - 0.005 * i for i in range(6)],
            "car": [0.09 + 0.01 * i for i in range(6)],
            "equity_to_assets": [0.05 + 0.01 * i for i in range(6)],
            "loan_loss_reserves_to_npls": [0.5 + 0.2 * i for i in range(6)],
        },
        index=[f"B{i}" for i in range(6)],
    )
    out = analytics.fundamental_radar(peers, "B5", is_bank=True)
    assert out["available"] is True and out["is_bank"] is True
    profitability = next(a for a in out["axes"] if a["axis"] == "Profitability")
    assert "net_interest_margin" in {m["metric"] for m in profitability["metrics"]}


# --------------------------------------------------------------------------- #
# analytics — beta
# --------------------------------------------------------------------------- #
def test_beta_of_a_series_against_itself_is_one():
    idx = pd.date_range("2024-01-01", periods=120, freq="D")
    s = pd.Series([100 + (i % 7) for i in range(120)], index=idx, dtype=float)
    assert analytics.beta(s, s) == pytest.approx(1.0)


def test_beta_needs_enough_overlap():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    s = pd.Series(range(10), index=idx, dtype=float)
    assert analytics.beta(s, s) is None
