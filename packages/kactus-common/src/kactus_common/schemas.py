"""Shared Pydantic schemas and serialisation helpers."""

from typing import Annotated, Any, Generic, TypeVar, get_args

from pydantic import (
    BaseModel,
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

# FancyFloat serializes float → str in JSON for precision
FancyFloat = Annotated[
    float, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")
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
