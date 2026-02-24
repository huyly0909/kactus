"""Custom SQLAlchemy column types for OLTP databases."""

from __future__ import annotations

import datetime
import struct
import typing
import zlib
from typing import Annotated, Any, TypeVar
from uuid import UUID

import orjson
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Dialect, TypeDecorator
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMBLOB
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.sql.type_api import TypeEngine

PydanticModel = TypeVar("PydanticModel", bound="BaseModel")

UnsignedBigInt = Annotated[int, lambda x: x > 0]

SIZE_BYTE = 4


def _to_utc(v: datetime.datetime) -> datetime.datetime:
    """Convert a datetime object to UTC."""
    if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
        v = v.replace(tzinfo=datetime.UTC)
    return v.astimezone(datetime.UTC)


def mysql_compress(value: bytes) -> typing.Optional[bytes]:
    if value is None:
        return None
    if value == b"":
        return b""
    size: bytes = struct.pack("I", len(value))
    data: bytes = zlib.compress(value)
    return size + data


def mysql_uncompress(value: bytes) -> bytes:
    if not value or len(value) < SIZE_BYTE:
        return value
    return zlib.decompress(value[SIZE_BYTE:])


def compress_json(data: typing.Any) -> bytes:
    return mysql_compress(orjson.dumps(data))


def uncompress_json(data: bytes) -> typing.Any:
    return orjson.loads(mysql_uncompress(data))


class DateTimeTzAware(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: "Dialect") -> TypeEngine[Any]:
        if dialect.name == "mysql":
            return dialect.type_descriptor(DATETIME(fsp=6))
        elif dialect.name == "postgresql":
            return dialect.type_descriptor(TIMESTAMP(timezone=True))
        return dialect.type_descriptor(DateTime())

    def process_result_value(
        self,
        value: datetime.datetime,
        dialect: "Dialect",
    ) -> datetime.datetime | None:
        if not value:
            return value
        return _to_utc(value)


class CompressedJSONType(TypeDecorator):
    impl = MEDIUMBLOB
    cache_ok = True

    def process_bind_param(self, py_value: Any, dialect: "Dialect") -> bytes | None:
        from fastapi.encoders import jsonable_encoder

        return compress_json(jsonable_encoder(py_value))

    def process_result_value(self, db_value: bytes, dialect: "Dialect") -> Any:
        return uncompress_json(db_value)


class UUIDList(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: list[UUID], dialect: "Dialect") -> list[str]:
        return [str(item) for item in value]

    def process_result_value(self, value: list[str], dialect: "Dialect") -> list[UUID]:
        if not value:
            return []
        return [UUID(item) for item in value]


class MutableList(Mutable, list):
    def extend(self, value: Any):
        list.extend(self, value)
        self.changed()

    def append(self, value: Any):
        list.append(self, value)
        self.changed()

    def remove(self, value: Any):
        list.remove(self, value)
        self.changed()

    @classmethod
    def coerce(cls, key: str, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        if isinstance(value, list):
            return cls(value)
        return Mutable.coerce(key, value)


class MutableDict(Mutable, dict):
    @classmethod
    def coerce(cls, key: str, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(value)
        return Mutable.coerce(key, value)

    def __setitem__(self, key: Any, value: Any):
        dict.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, key: Any):
        dict.__delitem__(self, key)
        self.changed()

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        if args or kwargs:
            self.changed()


MutableJSONList = MutableList.as_mutable(JSON)
MutableJSONDict = MutableDict.as_mutable(JSON)


class PydanticJSONDict(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, pydantic_model: type["PydanticModel"]):
        super().__init__()
        self.pydantic_model = pydantic_model

    def process_bind_param(
        self, value: "PydanticModel" | None, dialect: "Dialect"
    ) -> dict[str, Any] | None:
        if value is None:
            return value
        return value.model_dump(mode="json")

    def process_result_value(self, value, dialect: "Dialect") -> "PydanticModel" | None:
        if value is None:
            return None
        return self.pydantic_model.model_validate(value)


class PydanticJSONList(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, pydantic_model: type["PydanticModel"]):
        super().__init__()
        self.pydantic_model = pydantic_model

    def process_bind_param(
        self, value: list["PydanticModel"] | None, dialect: "Dialect"
    ) -> list[dict[str, Any]] | None:
        if value is None:
            return value
        return [item.model_dump(mode="json") for item in value]

    def process_result_value(
        self, value, dialect: "Dialect"
    ) -> list["PydanticModel"] | None:
        if value is None:
            return None
        return [self.pydantic_model.model_validate(item) for item in value]
