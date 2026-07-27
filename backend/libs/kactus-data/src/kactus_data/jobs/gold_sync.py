"""Gold sync-job handlers — backfill + sync-now.

Importing this module registers the ``GOLD_BACKFILL`` and ``GOLD_SYNC`` handlers
into :data:`kactus_data.jobs.sync_queue.SYNC_HANDLERS`, so the single data-plane
dispatcher can execute them. The gold sources (SJC / Mihong / Yahoo) do the
fetching; these handlers chunk the work, persist per-chunk progress (resume via
``cursor``), and write the typed OLAP tables (``gold_price_history`` for
backfill, ``gold_price_board`` + ``gold_price_tick`` for sync-now).

Backfill coverage per source (each job is one ``(source, code)`` series):

===========  =========================  ===============  ============
source       code (written)             unit             reaches back
===========  =========================  ===============  ============
``sjc``      ``SJC`` bar                 VND/lượng        ~2009
``yahoo``    ``XAU`` (OHLC)              USD/oz           2000-08-30
``mihong``   ``999`` ring               VND/lượng        ~1 year
===========  =========================  ===============  ============

The SJC feed serves only the bar's history, so the 999 ring backfills from
Mihong's trailing 1-year window (monthly points beyond a month) — the SJC bar is
the only series reaching 2009.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from kactus_common.datetimes import utcnow_naive
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_common.sync.const import SyncJobType
from kactus_data.jobs.crawl import _emit_refreshed
from kactus_data.jobs.sync_queue import (
    ProgressFn,
    SyncJobDeps,
    SyncJobView,
    register_handler,
)
from kactus_data.portfolio.provider import GoldAssetProvider
from kactus_data.sources.gold.history_tables import GOLD_PRICE_HISTORY_TABLE
from kactus_data.sources.gold.mihong import MihongGoldSource
from kactus_data.sources.gold.portfolio_tables import (
    GOLD_PRICE_BOARD_TABLE,
    GOLD_PRICE_TICK_TABLE,
    UNIT_USD_PER_OZ,
    UNIT_VND_PER_LUONG,
)
from kactus_data.sources.gold.sjc import (
    HISTORY_WINDOW_DAYS,
    SjcGoldSource,
    history_windows,
)
from kactus_data.sources.gold.yahoo import CODE as XAU_CODE
from kactus_data.sources.gold.yahoo import YahooGoldSource
from kactus_data.sources.stock.market import _to_table_df
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_data.util.time import to_event_dt
from loguru import logger

_QUANT = Decimal("0.0001")

#: The series a full sync-now touches, in fetch order. Both SJC codes come off
#: one board fetch; 999 is logged from *both* SJC and Mihong so each sub-tab has
#: its own tick, while the board keeps only the authoritative (non-Mihong) one.
_SYNC_SERIES: list[tuple[str, str]] = [
    ("sjc", "SJC"),
    ("sjc", "999"),
    ("mihong", "999"),
    ("yahoo", XAU_CODE),
]

_VALID_SYNC_SOURCES = frozenset({"sjc", "mihong", "yahoo"})


# --------------------------------------------------------------------------- #
# Row shaping helpers
# --------------------------------------------------------------------------- #
def _dec(value: object) -> Decimal | None:
    """4dp ``Decimal`` from a source number; ``None`` on blank/garbage.

    Via ``str`` (never ``float``) so VND gold stays exact; ``quantize`` also
    kills the binary-float noise Yahoo emits (``273.8999938964844``).
    """
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(_QUANT)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _history_row(
    *,
    code: str,
    source: str,
    unit: str,
    day: date,
    imported_at,
    buy: Decimal | None = None,
    sell: Decimal | None = None,
    ohlc: (
        tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None] | None
    ) = None,
) -> dict:
    """One ``gold_price_history`` row; ``event_dt`` derived from the native day."""
    row: dict = {
        "code": code,
        "date": day,
        "unit": unit,
        "source": source,
        "imported_at": imported_at,
        # Native ``date`` is the VN trading day; ``event_dt`` is its UTC instant.
        "event_dt": to_event_dt(day),
    }
    if buy is not None or sell is not None:
        row["buy_price"] = buy
        row["sell_price"] = sell
    if ohlc is not None:
        row["open"], row["high"], row["low"], row["close"] = ohlc
    return row


def _resolve_code(source: str, requested: object) -> str:
    """The code a backfill actually writes for ``source`` (feed-constrained).

    SJC history is the bar only and Yahoo is XAU only, so those are forced;
    Mihong honours a requested domestic code, defaulting to the 999 ring.
    """
    if source == "sjc":
        return "SJC"
    if source == "yahoo":
        return XAU_CODE
    code = str(requested or "999").upper()
    return code or "999"


def _store_history(storage: DuckDBStorage, rows: list[dict]) -> int:
    if not rows:
        return 0
    return storage.store(
        GOLD_PRICE_HISTORY_TABLE, _to_table_df(rows, GOLD_PRICE_HISTORY_TABLE)
    )


# --------------------------------------------------------------------------- #
# Backfill — blocking per-window fetch+store (run via asyncio.to_thread)
# --------------------------------------------------------------------------- #
def _year_chunks(start: date, end: date):
    """Yield one ``(from, to)`` per calendar year covering ``start..end``."""
    cur = start
    while cur <= end:
        year_end = min(date(cur.year, 12, 31), end)
        yield cur, year_end
        cur = year_end + timedelta(days=1)


def _fetch_store_sjc(storage: DuckDBStorage, frm: date, to: date) -> int:
    imported_at = utcnow_naive()
    rows = [
        _history_row(
            code="SJC",
            source="sjc",
            unit=UNIT_VND_PER_LUONG,
            day=point["date"],
            imported_at=imported_at,
            buy=point["buy_price"],
            sell=point["sell_price"],
        )
        for point in SjcGoldSource().history(frm, to)
    ]
    return _store_history(storage, rows)


def _fetch_store_yahoo(storage: DuckDBStorage, code: str, frm: date, to: date) -> int:
    response = YahooGoldSource().sync(frm, to, code)
    if not response.success or not response.data:
        return 0
    imported_at = utcnow_naive()
    rows = [
        _history_row(
            code=code,
            source="yahoo",
            unit=UNIT_USD_PER_OZ,
            day=date.fromisoformat(bar["date"]),
            imported_at=imported_at,
            ohlc=(
                _dec(bar.get("open")),
                _dec(bar.get("high")),
                _dec(bar.get("low")),
                _dec(bar.get("close")),
            ),
        )
        for bar in response.data
    ]
    return _store_history(storage, rows)


def _fetch_store_mihong(storage: DuckDBStorage, code: str, frm: date, to: date) -> int:
    imported_at = utcnow_naive()
    rows = [
        _history_row(
            code=code,
            source="mihong",
            unit=UNIT_VND_PER_LUONG,
            day=point["date"],
            imported_at=imported_at,
            buy=point["buy_price"],
            sell=point["sell_price"],
        )
        for point in MihongGoldSource().history(frm, to, code)
    ]
    return _store_history(storage, rows)


def _resume_after(view: SyncJobView) -> date | None:
    """The last-completed window end from a resumed job's cursor, if any."""
    if not view.cursor:
        return None
    try:
        return date.fromisoformat(view.cursor)
    except ValueError:
        return None


async def _run_windowed_backfill(
    deps: SyncJobDeps,
    view: SyncJobView,
    on_progress: ProgressFn,
    *,
    source: str,
    code: str,
    windows: list[tuple[date, date]],
    fetch_store,
) -> dict:
    """Drive ``windows`` through ``fetch_store``, checkpointing after each.

    Resume-safe: windows already covered by a previous run (``to <= cursor``)
    are skipped but still counted, so progress and the FIFO position hold.
    """
    total = len(windows)
    resume_after = _resume_after(view)
    written = 0
    for index, (frm, to) in enumerate(windows, start=1):
        if resume_after is not None and to <= resume_after:
            await on_progress(index, total, cursor=to.isoformat())
            continue
        written += await asyncio.to_thread(fetch_store, deps.storage, frm, to)
        await on_progress(index, total, cursor=to.isoformat())
    logger.info(
        f"gold backfill {source}:{code} wrote {written} rows over {total} window(s)"
    )
    return {"total": total, "rows": written, "source": source, "code": code}


@register_handler(SyncJobType.GOLD_BACKFILL)
async def gold_backfill(
    view: SyncJobView, deps: SyncJobDeps, on_progress: ProgressFn
) -> dict:
    """Backfill one ``(source, code)`` gold series over a date range."""
    params = view.params
    source = str(params.get("source", "")).lower()
    date_from = date.fromisoformat(params["date_from"])
    date_to = date.fromisoformat(params["date_to"])
    if date_to < date_from:
        raise ValueError(f"date_to {date_to} is before date_from {date_from}")
    code = _resolve_code(source, params.get("code"))

    if source == "sjc":
        windows = list(history_windows(date_from, date_to, HISTORY_WINDOW_DAYS))
        return await _run_windowed_backfill(
            deps,
            view,
            on_progress,
            source=source,
            code=code,
            windows=windows,
            fetch_store=_fetch_store_sjc,
        )
    if source == "yahoo":
        windows = list(_year_chunks(date_from, date_to))
        return await _run_windowed_backfill(
            deps,
            view,
            on_progress,
            source=source,
            code=code,
            windows=windows,
            fetch_store=lambda storage, frm, to: _fetch_store_yahoo(
                storage, code, frm, to
            ),
        )
    if source == "mihong":
        # Mihong's trailing window is one shot — no internal pagination.
        windows = [(date_from, date_to)]
        return await _run_windowed_backfill(
            deps,
            view,
            on_progress,
            source=source,
            code=code,
            windows=windows,
            fetch_store=lambda storage, frm, to: _fetch_store_mihong(
                storage, code, frm, to
            ),
        )
    raise ValueError(f"Unknown gold backfill source: {source!r}")


# --------------------------------------------------------------------------- #
# Sync-now — refresh the board + append an intraday tick per (source, code)
# --------------------------------------------------------------------------- #
def _collect_sync_rows(sources: list[str], now) -> list[dict]:
    """Fetch a board/tick row per configured (source, code) in ``sources``.

    Reuses the provider's per-series row builders so sync-now and the scheduler
    crawl shape rows identically. A board row already carries every tick column.
    """
    rows: list[dict] = []
    if "sjc" in sources:
        sjc = SjcGoldSource()
        board = sjc.fetch_board()
        for code in ("SJC", "999"):
            row = GoldAssetProvider._sjc_row(sjc, code, board, now)
            if row is not None:
                rows.append(row)
    if "mihong" in sources:
        row = GoldAssetProvider._mihong_row(
            MihongGoldSource(), "999", date.today(), now
        )
        if row is not None:
            rows.append(row)
    if "yahoo" in sources:
        row = GoldAssetProvider._yahoo_row(YahooGoldSource(), now)
        if row is not None:
            rows.append(row)
    return rows


def _authoritative_board(rows: list[dict]) -> list[dict]:
    """One row per code for the board, preferring a non-Mihong source."""
    by_code: dict[str, dict] = {}
    for row in rows:
        code = row["code"]
        current = by_code.get(code)
        if current is None or (
            current["source"] == "mihong" and row["source"] != "mihong"
        ):
            by_code[code] = row
    return list(by_code.values())


def _store_sync_rows(storage: DuckDBStorage, rows: list[dict]) -> int:
    """Append every row as a tick; upsert the authoritative rows to the board."""
    if not rows:
        return 0
    ticks = storage.store(
        GOLD_PRICE_TICK_TABLE, _to_table_df(rows, GOLD_PRICE_TICK_TABLE)
    )
    board = _authoritative_board(rows)
    storage.store(GOLD_PRICE_BOARD_TABLE, _to_table_df(board, GOLD_PRICE_BOARD_TABLE))
    return ticks


@register_handler(SyncJobType.GOLD_SYNC)
async def gold_sync(
    view: SyncJobView, deps: SyncJobDeps, on_progress: ProgressFn
) -> dict:
    """Fetch current gold quotes now: refresh the board + log intraday ticks."""
    target = str(view.params.get("source", "all")).lower()
    if target in ("", "all"):
        sources = ["sjc", "mihong", "yahoo"]
    elif target in _VALID_SYNC_SOURCES:
        sources = [target]
    else:
        raise ValueError(f"Unknown gold sync source: {target!r}")

    total = len(sources)
    now = utcnow_naive()
    all_rows: list[dict] = []
    for index, source in enumerate(sources, start=1):
        all_rows.extend(await asyncio.to_thread(_collect_sync_rows, [source], now))
        await on_progress(index, total, cursor=source)

    # Store once across all sources: every fetched (source, code) becomes a tick,
    # but the board takes a single authoritative row per code — done per-source it
    # would let Mihong's 999 overwrite SJC's on the board.
    ticks = await asyncio.to_thread(_store_sync_rows, deps.storage, all_rows)
    codes = {row["code"] for row in all_rows}

    # Nudge the market Overview to refetch (benign no-op with no SSE handler).
    if codes:
        await _emit_refreshed(
            asset_type=str(AssetType.GOLD),
            kind=str(CrawlKind.QUOTES),
            codes=sorted(codes),
            crawl_run_id=None,
        )
    logger.info(f"gold sync-now logged {ticks} tick(s) for {sorted(codes)}")
    return {"total": total, "ticks": ticks, "codes": sorted(codes)}
