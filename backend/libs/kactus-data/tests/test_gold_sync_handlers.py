"""Handler tests for gold backfill + sync-now.

Runs the real ``GOLD_BACKFILL`` / ``GOLD_SYNC`` handlers inline against a local
DuckDB file, stubbing the network sources. Covers: SJC history → history table,
Yahoo OHLC chunked by year, resume skipping completed windows, and sync-now
logging a per-source tick per (source, code) while the board keeps one
authoritative (non-Mihong) row per code.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from kactus_common.datetimes import utcnow_naive
from kactus_data.jobs.gold_sync import gold_backfill, gold_sync
from kactus_data.jobs.sync_queue import SyncJobDeps, SyncJobView
from kactus_data.portfolio.provider import GoldAssetProvider
from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.gold.sjc import SjcGoldSource
from kactus_data.sources.gold.yahoo import YahooGoldSource
from kactus_data.storage.duckdb import DuckDBStorage


@pytest.fixture
def storage(tmp_path):
    return DuckDBStorage(str(tmp_path / "gold.duckdb"))


def _deps(storage):
    return SyncJobDeps(db=None, storage=storage, providers={})


def _view(job_type, params, *, cursor=None):
    return SyncJobView(
        id=1,
        job_type=job_type,
        dedup_key="k",
        params=params,
        cursor=cursor,
        progress_done=0,
        progress_total=0,
    )


class _Progress:
    def __init__(self):
        self.calls: list[tuple] = []

    async def __call__(self, done, total, cursor=None):
        self.calls.append((done, total, cursor))


@pytest.mark.asyncio
async def test_backfill_sjc_writes_history(monkeypatch, storage):
    def fake_history(self, frm, to):
        return [
            {
                "date": date(2009, 1, 1),
                "buy_price": Decimal("1000000"),
                "sell_price": Decimal("1010000"),
            },
            {
                "date": date(2009, 1, 2),
                "buy_price": Decimal("1002000"),
                "sell_price": Decimal("1012000"),
            },
        ]

    monkeypatch.setattr(SjcGoldSource, "history", fake_history)
    prog = _Progress()
    view = _view(
        "gold_backfill",
        {"source": "sjc", "date_from": "2009-01-01", "date_to": "2009-01-05"},
    )

    result = await gold_backfill(view, _deps(storage), prog)

    df = storage.query("SELECT * FROM gold_price_history ORDER BY date")
    assert len(df) == 2
    assert set(df["source"]) == {"sjc"}
    assert set(df["code"]) == {"SJC"}
    assert set(df["unit"]) == {"VND/luong"}
    assert df["event_dt"].notna().all()  # derived UTC axis populated
    assert result["source"] == "sjc" and result["rows"] == 2
    # 5-day range = one 80-day window = one progress tick at done == total.
    assert prog.calls[-1][0] == prog.calls[-1][1] == 1


@pytest.mark.asyncio
async def test_backfill_yahoo_chunks_by_year_and_writes_ohlc(monkeypatch, storage):
    seen: list[tuple[date, date]] = []

    def fake_sync(self, frm, to, code="XAU"):
        seen.append((frm, to))
        return SyncDataResponse(
            success=True,
            data_source="yahoo",
            code=code,
            start_date=frm.isoformat(),
            end_date=to.isoformat(),
            data=[
                {
                    "date": frm.isoformat(),
                    "open": 100.5,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.25,
                }
            ],
            timestamp="2026-01-01",
        )

    monkeypatch.setattr(YahooGoldSource, "sync", fake_sync)
    prog = _Progress()
    view = _view(
        "gold_backfill",
        {"source": "yahoo", "date_from": "2000-08-30", "date_to": "2001-03-01"},
    )

    result = await gold_backfill(view, _deps(storage), prog)

    # Two calendar years → two chunks → two progress ticks.
    assert len(seen) == 2
    assert len(prog.calls) == 2
    df = storage.query("SELECT * FROM gold_price_history")
    assert set(df["unit"]) == {"USD/oz"}
    assert df["close"].notna().all()
    assert df["open"].notna().all()
    assert df["buy_price"].isna().all()  # world gold has no bid/ask
    assert result["code"] == "XAU"


@pytest.mark.asyncio
async def test_backfill_resume_skips_completed_windows(monkeypatch, storage):
    seen: list[tuple[date, date]] = []

    def fake_history(self, frm, to):
        seen.append((frm, to))
        return [{"date": frm, "buy_price": Decimal("1"), "sell_price": Decimal("2")}]

    monkeypatch.setattr(SjcGoldSource, "history", fake_history)
    prog = _Progress()
    # ~200 days → 3 windows; cursor at the end of window 1 resumes at window 2.
    view = _view(
        "gold_backfill",
        {"source": "sjc", "date_from": "2009-01-01", "date_to": "2009-07-20"},
        cursor="2009-03-21",
    )

    await gold_backfill(view, _deps(storage), prog)

    assert (date(2009, 1, 1), date(2009, 3, 21)) not in seen  # window 1 skipped
    assert len(seen) == 2  # only windows 2 and 3 fetched
    assert prog.calls[-1][1] == 3  # total still reported as all 3 windows


def _board_row(code, source, price, now):
    return {
        "code": code,
        "buy_price": Decimal(price),
        "sell_price": Decimal(price),
        "unit": "VND/luong" if source != "yahoo" else "USD/oz",
        "source": source,
        "crawled_at": now,
        "raw_json": "{}",
    }


@pytest.mark.asyncio
async def test_sync_now_logs_per_source_ticks_and_authoritative_board(
    monkeypatch, storage
):
    now = utcnow_naive()
    monkeypatch.setattr(SjcGoldSource, "fetch_board", lambda self: [{"present": True}])
    monkeypatch.setattr(
        GoldAssetProvider,
        "_sjc_row",
        staticmethod(lambda sjc, code, board, ts: _board_row(code, "sjc", "100", now)),
    )
    monkeypatch.setattr(
        GoldAssetProvider,
        "_mihong_row",
        classmethod(
            lambda cls, mihong, code, today, ts: _board_row("999", "mihong", "99", now)
        ),
    )
    monkeypatch.setattr(
        GoldAssetProvider,
        "_yahoo_row",
        staticmethod(lambda yahoo, ts: _board_row("XAU", "yahoo", "4000", now)),
    )

    prog = _Progress()
    result = await gold_sync(
        _view("gold_sync", {"source": "all"}), _deps(storage), prog
    )

    ticks = storage.query("SELECT * FROM gold_price_tick")
    # One tick per (source, code): both SJC codes, Mihong 999, Yahoo XAU.
    assert set(zip(ticks["source"], ticks["code"])) == {
        ("sjc", "SJC"),
        ("sjc", "999"),
        ("mihong", "999"),
        ("yahoo", "XAU"),
    }
    assert len(ticks) == 4
    assert result["ticks"] == 4

    board = storage.query("SELECT * FROM gold_price_board")
    # Board keeps one authoritative row per code — 999 is SJC's, not Mihong's.
    assert dict(zip(board["code"], board["source"])) == {
        "SJC": "sjc",
        "999": "sjc",
        "XAU": "yahoo",
    }
    assert len(prog.calls) == 3  # one tick per source


@pytest.mark.asyncio
async def test_sync_now_single_source(monkeypatch, storage):
    now = utcnow_naive()
    monkeypatch.setattr(
        GoldAssetProvider,
        "_yahoo_row",
        staticmethod(lambda yahoo, ts: _board_row("XAU", "yahoo", "4000", now)),
    )
    result = await gold_sync(
        _view("gold_sync", {"source": "yahoo"}), _deps(storage), _Progress()
    )

    assert result["codes"] == ["XAU"]
    ticks = storage.query("SELECT * FROM gold_price_tick")
    assert set(ticks["source"]) == {"yahoo"}


@pytest.mark.asyncio
async def test_backfill_rejects_unknown_source(storage):
    view = _view(
        "gold_backfill",
        {"source": "doji", "date_from": "2020-01-01", "date_to": "2020-02-01"},
    )
    with pytest.raises(ValueError, match="Unknown gold backfill source"):
        await gold_backfill(view, _deps(storage), _Progress())
