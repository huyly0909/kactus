"""Parse + import historical gold-price CSVs into ``gold_price_history``.

Three one-off backfill formats are recognised by their exact header row:

- SJC bar (sjc.com.vn):    ``date,buy_vnd_per_luong,sell_vnd_per_luong``
- World gold (Yahoo GC=F): ``date,open_usd_oz,high_usd_oz,low_usd_oz,close_usd_oz``
- PNJ multi-series:        ``date,location,gold_type,buy_vnd_per_luong,sell_vnd_per_luong,updated_at``

Money goes ``str → Decimal.quantize(4dp)`` and never through ``float`` — VND
gold (~1.4e8) exceeds FLOAT exactness, and the XAU file carries binary-float
noise (``273.8999938964844``) that quantizing kills. Rows with an unparseable
date or price are skipped and counted, not fatal; an unrecognised header is a
:class:`ValidationError` (the file is not one of ours).
"""

from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from io import BytesIO

import pandas as pd
from kactus_common.datetimes import utcnow_naive
from kactus_common.exceptions import ValidationError
from kactus_common.market.schema import GoldImportResultSchema
from kactus_data.sources.gold.history_tables import GOLD_PRICE_HISTORY_TABLE
from kactus_data.sources.gold.portfolio_tables import (
    UNIT_USD_PER_OZ,
    UNIT_VND_PER_LUONG,
)
from kactus_data.sources.gold.yahoo import CODE as XAU_CODE
from kactus_data.sources.stock.market import _to_table_df
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_data.util.time import to_event_dt


class GoldHistoryDataset(StrEnum):
    """Recognised backfill CSV formats."""

    SJC = "sjc"
    XAU = "xau"
    PNJ = "pnj"


SJC_CODE = "SJC"

_HEADERS: dict[tuple[str, ...], GoldHistoryDataset] = {
    ("date", "buy_vnd_per_luong", "sell_vnd_per_luong"): GoldHistoryDataset.SJC,
    (
        "date",
        "open_usd_oz",
        "high_usd_oz",
        "low_usd_oz",
        "close_usd_oz",
    ): GoldHistoryDataset.XAU,
    (
        "date",
        "location",
        "gold_type",
        "buy_vnd_per_luong",
        "sell_vnd_per_luong",
        "updated_at",
    ): GoldHistoryDataset.PNJ,
}

_SOURCES = {
    GoldHistoryDataset.SJC: "sjc",
    GoldHistoryDataset.XAU: "yahoo",
    GoldHistoryDataset.PNJ: "pnj",
}

_QUANT = Decimal("0.0001")
_PNJ_UPDATED_AT_FORMAT = "%d/%m/%Y %H:%M:%S"
#: Keep only the first few row-level messages — enough to diagnose, without
#: echoing a 92k-row file back in the response.
_MAX_ERROR_MESSAGES = 5


def detect_dataset(columns: list[str]) -> GoldHistoryDataset | None:
    """Match a CSV header row to a known backfill format (exact match)."""
    return _HEADERS.get(tuple(c.strip() for c in columns))


def _money(value: str | None) -> Decimal | None:
    """``str → Decimal`` at 4dp; blank → None; garbage raises InvalidOperation."""
    if value is None or not value.strip():
        return None
    return Decimal(value.strip()).quantize(_QUANT)


def parse_history_csv(
    content: bytes,
) -> tuple[GoldHistoryDataset, pd.DataFrame, int, int, list[str]]:
    """Parse one CSV into table-shaped rows.

    Returns ``(dataset, df, rows_parsed, rows_skipped, errors)`` where ``df``
    has exactly the ``gold_price_history`` columns in table order.
    """
    try:
        raw = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise ValidationError(
            "Could not read the file as CSV",
            tip="Upload one of the gold history CSVs produced by the backfill scripts",
        ) from exc

    dataset = detect_dataset(list(raw.columns))
    if dataset is None:
        raise ValidationError(
            "Unrecognised CSV header",
            tip="Expected an SJC, world-XAU or PNJ gold history file",
            data={"columns": list(raw.columns)},
        )

    imported_at = utcnow_naive()
    source = _SOURCES[dataset]
    rows: list[dict] = []
    errors: list[str] = []
    skipped = 0

    for line, record in enumerate(raw.to_dict("records"), start=2):
        try:
            row_date = datetime.date.fromisoformat(record["date"].strip())
            row = {
                "date": row_date,
                "unit": UNIT_VND_PER_LUONG,
                "source": source,
                "imported_at": imported_at,
                # Native ``date`` stays the Vietnam trading day; ``event_dt`` is
                # its canonical UTC instant (midnight VN → UTC).
                "event_dt": to_event_dt(row_date),
            }
            if dataset == GoldHistoryDataset.SJC:
                row["code"] = SJC_CODE
                row["buy_price"] = _money(record["buy_vnd_per_luong"])
                row["sell_price"] = _money(record["sell_vnd_per_luong"])
            elif dataset == GoldHistoryDataset.XAU:
                row["code"] = XAU_CODE
                row["unit"] = UNIT_USD_PER_OZ
                row["open"] = _money(record["open_usd_oz"])
                row["high"] = _money(record["high_usd_oz"])
                row["low"] = _money(record["low_usd_oz"])
                row["close"] = _money(record["close_usd_oz"])
            else:
                location = record["location"].strip()
                gold_type = record["gold_type"].strip()
                if not location or not gold_type:
                    raise ValueError("missing location/gold_type")
                row["code"] = f"PNJ:{location}:{gold_type}"
                row["location"] = location
                row["gold_type"] = gold_type
                row["buy_price"] = _money(record["buy_vnd_per_luong"])
                row["sell_price"] = _money(record["sell_vnd_per_luong"])
                updated_at = record["updated_at"].strip()
                # A bad snapshot timestamp is not worth losing the price row.
                try:
                    row["updated_at"] = datetime.datetime.strptime(
                        updated_at, _PNJ_UPDATED_AT_FORMAT
                    )
                except ValueError:
                    row["updated_at"] = None
            rows.append(row)
        except (ValueError, InvalidOperation, KeyError) as exc:
            skipped += 1
            if len(errors) < _MAX_ERROR_MESSAGES:
                errors.append(f"line {line}: {exc}")

    rows_parsed = len(raw)
    df = pd.DataFrame(rows)
    if not df.empty:
        # PK is (code, date); keep the freshest duplicate (PNJ re-publishes
        # intraday — updated_at orders them; NaT/absent sorts first).
        sort_cols = ["code", "date"] + (
            ["updated_at"] if "updated_at" in df.columns else []
        )
        df = df.sort_values(sort_cols).drop_duplicates(["code", "date"], keep="last")
    df = _to_table_df(df.to_dict("records"), GOLD_PRICE_HISTORY_TABLE)
    return dataset, df, rows_parsed, skipped, errors


def import_history(
    storage: DuckDBStorage,
    content: bytes,
    filename: str | None = None,
) -> GoldImportResultSchema:
    """Parse ``content`` and upsert it into ``gold_price_history``.

    Idempotent: the table's ``(code, date)`` PK + UPSERT means re-importing
    the same file yields the same row counts. Blocking — callers on the event
    loop wrap this in ``asyncio.to_thread``.
    """
    dataset, df, rows_parsed, skipped, errors = parse_history_csv(content)
    imported = 0
    if not df.empty:
        imported = storage.store(GOLD_PRICE_HISTORY_TABLE, df)
    return GoldImportResultSchema(
        dataset=dataset,
        filename=filename,
        rows_parsed=rows_parsed,
        rows_imported=imported,
        rows_skipped=skipped,
        codes=0 if df.empty else int(df["code"].nunique()),
        errors=errors,
    )
