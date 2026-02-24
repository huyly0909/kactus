"""Event dispatching system for background tasks and synchronous handlers."""

import asyncio
import functools
import uuid
from abc import ABC, abstractmethod
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Callable, Protocol, Self

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from fastapi import FastAPI

_sep = "-"


def qualname(o: object | Callable) -> str:
    """Convert an attribute/class/function to a string importable path."""
    if callable(o) and hasattr(o, "__module__") and hasattr(o, "__qualname__"):
        return f"{o.__module__}.{o.__qualname__}"

    cls = o
    if not isinstance(cls, type):
        cls = type(cls)

    name = cls.__qualname__
    module = cls.__module__

    if module and module != "__builtin__":
        return f"{module}.{name}"

    return name


class BaseEventName(StrEnum):
    def fqn(self) -> str:
        return _sep.join([self.__module__, self.__class__.__qualname__, self.value])

    @classmethod
    def from_fqn(cls, fqn: str) -> Self:
        module_name, class_name, event_name = fqn.split(_sep, maxsplit=2)
        module = __import__(module_name, fromlist=[class_name])
        klass = getattr(module, class_name)
        return klass(event_name)


class EnforceEventNameMeta(type(BaseModel)):
    def __new__(cls, name, bases, namespace):
        if not any(isinstance(b, EnforceEventNameMeta) for b in bases):
            return super().__new__(cls, name, bases, namespace)

        event_name = namespace.get("__event_name__", None)
        if event_name is None:
            raise TypeError(f"{name} must define '__event_name__'")

        if not isinstance(event_name, Enum) or not issubclass(
            type(event_name), BaseEventName
        ):
            raise TypeError(
                f"{name}.__event_name__ must be an enum member of a subclass of BaseEventName"
            )

        return super().__new__(cls, name, bases, namespace)


class BaseEventPayload(BaseModel, metaclass=EnforceEventNameMeta):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    __event_name__: BaseEventName = None

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)

    @property
    def event_name(self) -> BaseEventName:
        return self.__event_name__

    async def dispatch(self, background: bool = False):
        """Dispatch the payload by using the default dispatcher."""
        raise NotImplementedError


class EventHandlerFunc(Protocol):
    async def __call__(
        self, *, event_name: BaseEventName, payload: BaseEventPayload
    ) -> None: ...


class BaseDispatcher(ABC):
    def init_fastapi_app(self, app: "FastAPI"):
        """Optional: hook into FastAPI lifecycle."""

    @abstractmethod
    async def dispatch(self, payload: BaseEventPayload, background: bool = False):
        """Dispatch the given event payload."""

    @abstractmethod
    def register_handler(self, *events: BaseEventName):
        """Register a handler for the given event names."""

    @staticmethod
    def wrap_handler(func: EventHandlerFunc):
        async def wrapper(event_name: BaseEventName, payload: BaseEventPayload):
            await BaseDispatcher._handle(func, event_name, payload)

        return wrapper

    @staticmethod
    async def _handle(
        func: EventHandlerFunc, event_name: BaseEventName, payload: BaseEventPayload
    ):
        with logger.contextualize(event_id=str(payload.event_id)):
            logger.info(f"Handling event {event_name} with {qualname(func)}")
            if asyncio.iscoroutinefunction(func):
                await func(event_name=event_name, payload=payload)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    functools.partial(func, event_name=event_name, payload=payload),
                )
