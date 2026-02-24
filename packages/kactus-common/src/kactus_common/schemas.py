"""Shared Pydantic schemas and serialisation helpers."""

from typing import Annotated, Generic, TypeVar, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    PlainSerializer,
    ValidationInfo,
    field_validator,
)

FancyInt = Annotated[
    int, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")
]
FancyFloat = Annotated[
    float, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")
]


T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    code: str = "0"
    msg: str = "success"
    data: T


class Pagination(BaseModel, Generic[T]):
    """Paginated list response."""

    total: int
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
