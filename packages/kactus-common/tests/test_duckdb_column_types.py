"""Column → DuckDB DDL type rendering, and the money-safe FancyDecimal alias."""

from decimal import Decimal

import pytest
from kactus_common.database.duckdb.consts import DataType
from kactus_common.database.duckdb.schema import (
    DEFAULT_MONEY_PRECISION,
    DEFAULT_MONEY_SCALE,
    Column,
)
from kactus_common.schemas import BaseSchema, FancyDecimal, FancyFloat, decimal_to_str


class TestColumnSqlType:
    def test_decimal_defaults_to_money_shape(self):
        col = Column(name="buy_price", data_type=DataType.DECIMAL)
        assert (
            col.sql_type == f"DECIMAL({DEFAULT_MONEY_PRECISION},{DEFAULT_MONEY_SCALE})"
        )

    def test_decimal_honours_explicit_precision_and_scale(self):
        col = Column(name="rate", data_type=DataType.DECIMAL, precision=10, scale=6)
        assert col.sql_type == "DECIMAL(10,6)"

    def test_scale_zero_is_not_treated_as_unset(self):
        col = Column(name="dong", data_type=DataType.DECIMAL, precision=20, scale=0)
        assert col.sql_type == "DECIMAL(20,0)"

    @pytest.mark.parametrize(
        "data_type",
        [DataType.STRING, DataType.FLOAT, DataType.DOUBLE, DataType.TIMESTAMP],
    )
    def test_non_decimal_types_pass_through(self, data_type):
        col = Column(name="x", data_type=data_type)
        assert col.sql_type == str(data_type)
        assert "(" not in col.sql_type

    def test_default_money_shape_holds_vnd_market_caps(self):
        """20 integer digits — VN market caps reach ~1e15 dong."""
        integer_digits = DEFAULT_MONEY_PRECISION - DEFAULT_MONEY_SCALE
        assert 10**integer_digits > 1e15


class TestFancyDecimal:
    """Money is serialised as an exact decimal string, never a float."""

    class Quote(BaseSchema):
        price: FancyDecimal | None = None
        volume: FancyFloat | None = None

    def test_serialises_without_scale_padding(self):
        """DuckDB returns the column's full scale; the API should not echo it."""
        payload = self.Quote(price=Decimal("121000000.0000")).model_dump(mode="json")
        assert payload["price"] == "121000000"

    def test_keeps_significant_decimals(self):
        payload = self.Quote(price=Decimal("4037.6999")).model_dump(mode="json")
        assert payload["price"] == "4037.6999"

    def test_never_uses_scientific_notation(self):
        """normalize() alone would render round numbers as 2E+6."""
        assert decimal_to_str(Decimal("2000000.0000")) == "2000000"

    def test_preserves_value_a_float_would_round(self):
        """The whole point: gold prices past 2^24 stay exact."""
        exact = Decimal("136571425")
        assert self.Quote(price=exact).model_dump(mode="json")["price"] == "136571425"

    def test_accepts_decimal_from_duckdb_without_float_conversion(self):
        quote = self.Quote(price=Decimal("139142850.0000"))
        assert isinstance(quote.price, Decimal)

    def test_none_stays_none(self):
        assert self.Quote().model_dump(mode="json")["price"] is None

    def test_volumes_still_use_float(self):
        """Non-money fields keep FancyFloat — DECIMAL is for money only."""
        quote = self.Quote(volume=1234.5)
        assert isinstance(quote.volume, float)
