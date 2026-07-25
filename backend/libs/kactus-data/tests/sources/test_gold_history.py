"""Tests for the gold history CSV parser + importer."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from kactus_common.exceptions import ValidationError
from kactus_data.sources.gold.history import (
    GoldHistoryDataset,
    detect_dataset,
    import_history,
    parse_history_csv,
)
from kactus_data.sources.gold.history_tables import GOLD_PRICE_HISTORY_TABLE
from kactus_data.storage.duckdb import DuckDBStorage

SJC_CSV = b"""date,buy_vnd_per_luong,sell_vnd_per_luong
2026-07-23,134000000,139000000
2026-07-24,134500000,139500000
"""

XAU_CSV = b"""date,open_usd_oz,high_usd_oz,low_usd_oz,close_usd_oz
2000-08-30,273.8999938964844,274.0,272.5,273.8999938964844
2000-08-31,274.0,275.1,273.0,274.5
"""

PNJ_CSV = (
    "date,location,gold_type,buy_vnd_per_luong,sell_vnd_per_luong,updated_at\n"
    "2026-07-24,TPHCM,PNJ,134500000,139500000,24/07/2026 11:12:14\n"
    "2026-07-24,Hà Nội,Nhẫn Trơn PNJ 999.9,133000000,138000000,24/07/2026 11:12:14\n"
).encode()


class TestDetectDataset:
    def test_detects_all_three_formats(self):
        assert (
            detect_dataset(["date", "buy_vnd_per_luong", "sell_vnd_per_luong"])
            == GoldHistoryDataset.SJC
        )
        assert (
            detect_dataset(
                ["date", "open_usd_oz", "high_usd_oz", "low_usd_oz", "close_usd_oz"]
            )
            == GoldHistoryDataset.XAU
        )
        assert (
            detect_dataset(
                [
                    "date",
                    "location",
                    "gold_type",
                    "buy_vnd_per_luong",
                    "sell_vnd_per_luong",
                    "updated_at",
                ]
            )
            == GoldHistoryDataset.PNJ
        )

    def test_unknown_header_is_none(self):
        assert detect_dataset(["date", "price"]) is None

    def test_unknown_header_raises_validation_error(self):
        with pytest.raises(ValidationError):
            parse_history_csv(b"date,price\n2026-01-01,5\n")


class TestParse:
    def test_sjc_rows(self):
        dataset, df, parsed, skipped, errors = parse_history_csv(SJC_CSV)
        assert dataset == GoldHistoryDataset.SJC
        assert parsed == 2 and skipped == 0 and errors == []
        assert list(df.columns) == [c.name for c in GOLD_PRICE_HISTORY_TABLE.columns]
        row = df.iloc[1]
        assert row["code"] == "SJC"
        assert row["date"] == date(2026, 7, 24)
        # VND survives exactly as a Decimal — never through float.
        assert row["buy_price"] == Decimal("134500000.0000")
        assert row["unit"] == "VND/luong"
        assert row["source"] == "sjc"

    def test_xau_rows_quantize_float_noise(self):
        dataset, df, parsed, skipped, _ = parse_history_csv(XAU_CSV)
        assert dataset == GoldHistoryDataset.XAU
        assert parsed == 2 and skipped == 0
        row = df.iloc[0]
        assert row["code"] == "XAU"
        assert row["close"] == Decimal("273.9000")
        assert row["buy_price"] is None
        assert row["unit"] == "USD/oz"

    def test_pnj_rows_compose_code_and_parse_updated_at(self):
        dataset, df, parsed, skipped, _ = parse_history_csv(PNJ_CSV)
        assert dataset == GoldHistoryDataset.PNJ
        assert parsed == 2 and skipped == 0
        codes = set(df["code"])
        assert codes == {"PNJ:TPHCM:PNJ", "PNJ:Hà Nội:Nhẫn Trơn PNJ 999.9"}
        row = df[df["location"] == "TPHCM"].iloc[0]
        assert row["gold_type"] == "PNJ"
        assert row["updated_at"] == datetime(2026, 7, 24, 11, 12, 14)

    def test_bad_rows_are_skipped_and_counted(self):
        csv = (
            b"date,buy_vnd_per_luong,sell_vnd_per_luong\n"
            b"not-a-date,1,2\n"
            b"2026-07-24,garbage,139500000\n"
            b"2026-07-25,134500000,139500000\n"
        )
        _, df, parsed, skipped, errors = parse_history_csv(csv)
        assert parsed == 3
        assert skipped == 2
        assert len(df) == 1
        assert len(errors) == 2

    def test_duplicate_code_date_keeps_freshest(self):
        csv = (
            "date,location,gold_type,buy_vnd_per_luong,sell_vnd_per_luong,updated_at\n"
            "2026-07-24,TPHCM,PNJ,1000,2000,24/07/2026 09:00:00\n"
            "2026-07-24,TPHCM,PNJ,1500,2500,24/07/2026 15:00:00\n"
        ).encode()
        _, df, parsed, skipped, _ = parse_history_csv(csv)
        assert parsed == 2 and skipped == 0
        assert len(df) == 1
        assert df.iloc[0]["buy_price"] == Decimal("1500.0000")


class TestImport:
    def test_import_is_idempotent(self, tmp_path):
        storage = DuckDBStorage(str(tmp_path / "gold.duckdb"))
        try:
            first = import_history(storage, SJC_CSV, "sjc.csv")
            assert first.dataset == "sjc"
            assert first.filename == "sjc.csv"
            assert first.rows_imported == 2
            assert first.codes == 1

            second = import_history(storage, SJC_CSV, "sjc.csv")
            assert second.rows_imported == 2

            count = storage.query(
                f"SELECT COUNT(*) AS n FROM {GOLD_PRICE_HISTORY_TABLE.name}"
            )
            assert int(count.iloc[0]["n"]) == 2
        finally:
            storage.close()

    def test_import_mixed_datasets_share_table(self, tmp_path):
        storage = DuckDBStorage(str(tmp_path / "gold.duckdb"))
        try:
            import_history(storage, SJC_CSV)
            import_history(storage, XAU_CSV)
            import_history(storage, PNJ_CSV)
            codes = storage.query(
                f"SELECT DISTINCT code FROM {GOLD_PRICE_HISTORY_TABLE.name}"
            )
            assert len(codes) == 4  # SJC, XAU, 2 PNJ series
        finally:
            storage.close()
