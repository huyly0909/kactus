"""Shared Pydantic schemas and serialisation helpers."""

import datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar, get_args

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
    ValidationInfo,
    WithJsonSchema,
    field_validator,
)

# FancyInt serializes int → str in JSON to prevent JavaScript precision loss
FancyInt = Annotated[
    int, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")
]


def _ensure_utc(value: Any) -> Any:
    """Stamp a datetime as UTC-aware; pass anything else through unchanged.

    OLAP (DuckDB) timestamps are stored naive-UTC (no zone). Marking them aware
    here makes Pydantic serialise them with an explicit ``+00:00`` offset, so
    the client knows the zone and can convert to the user's timezone. Idempotent
    — an already-aware value is converted, not double-stamped — which matters
    because the shared market schemas are validated on both planes.
    """
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.UTC)
        return value.astimezone(datetime.UTC)
    return value


# AwareUTCDatetime: a datetime guaranteed to carry a UTC offset in JSON. Use it
# for any timestamp read out of the naive-UTC OLAP columns (``event_dt``,
# ``crawled_at``, ``synced_at``) so the frontend can localise it.
AwareUTCDatetime = Annotated[datetime.datetime, BeforeValidator(_ensure_utc)]

# FancyFloat serializes float → str in JSON for precision
FancyFloat = Annotated[
    float, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")
]


def decimal_to_str(value: Decimal) -> str:
    """Render a Decimal in plain notation, without padding or exponents.

    DuckDB hands back the column's full scale (``DECIMAL(24,4)`` →
    ``121000000.0000``); ``normalize()`` drops the padding but switches to
    scientific notation for round numbers (``2E+6``), so ``format(..., "f")``
    forces it back to plain digits.
    """
    return format(value.normalize(), "f")


# FancyDecimal is FancyFloat's exact-arithmetic counterpart — use it for money.
# Binary floats cannot represent VND prices (~1.4e8 for gold) exactly, so money
# stays a Decimal end to end: DECIMAL column → Decimal in Python → JSON string.
FancyDecimal = Annotated[
    Decimal, PlainSerializer(decimal_to_str, return_type=str, when_used="json")
]

# OpaqueDict: a `dict[str, Any]` whose generated JSON schema uses
# ``additionalProperties: {}`` (empty schema = "any") instead of the bare
# ``additionalProperties: true`` Pydantic emits by default. Use this for
# fields whose shape genuinely varies — keeps openapi-python-client and similar
# code generators happy without falsely promising a typed structure.
OpaqueDict = Annotated[
    dict[str, Any],
    WithJsonSchema(
        {
            "type": "object",
            "additionalProperties": {},
            "description": "Opaque object whose shape depends on context.",
        }
    ),
]


T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    code: str = "0"
    msg: str = "success"
    data: T


class Pagination(BaseModel, Generic[T]):
    """Paginated list response.

    ``page`` / ``page_size`` carry the echo of the request so the client can
    render pagination controls without remembering its own request.
    """

    total: int
    page: int = 1
    page_size: int = 0
    items: list[T]


class BaseSchema(BaseModel):
    """Base schema with sensible defaults for API request/response models.

    Features:
    - Strips whitespace from strings.
    - Converts empty strings to ``None`` for non-string fields.
    - Allows ORM attribute loading via ``from_attributes=True``.
    """

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def empty_string_2_none(cls, v: T, info: ValidationInfo) -> T | None:
        if v != "":
            return v

        field_name = info.field_name
        ann = cls.model_fields[field_name].annotation
        ann_types = get_args(ann) or (ann,)
        if str not in ann_types:
            return None
        return v


class MessageResponse(BaseSchema):
    """Standard message-only response (e.g. for deletes)."""

    message: str = "ok"


class OkResponse(BaseSchema):
    """Simple OK acknowledgement response."""

    message: str = "ok"
