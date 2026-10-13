"""Tests for the stock domain contract (wire values must not drift)."""

from __future__ import annotations

from kactus_stock_vn.const import OHLCVInterval, ReportPeriod, ReportType
from kactus_stock_vn.schema import FinanceReportSchema


def test_report_wire_values_unchanged():
    """The enums moved packages; the DB/wire strings must not have moved."""
    assert ReportType.INCOME_STATEMENT == "income_statement"
    assert ReportType.RATIO == "ratio"
    assert ReportPeriod.QUARTER == "quarter"
    assert OHLCVInterval.D1 == "1D"


def test_finance_report_schema_roundtrip():
    r = FinanceReportSchema(
        symbol="FPT",
        report_type="income_statement",
        period="year",
        year=2025,
        data={"revenue": "1"},
    )
    assert r.report_type is ReportType.INCOME_STATEMENT
    assert r.quarter is None
