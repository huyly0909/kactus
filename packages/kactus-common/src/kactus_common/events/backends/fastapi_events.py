"""FastAPI background event dispatcher using fastapi-events."""

from fastapi_events.dispatcher import dispatch
from fastapi_events.handlers.local import LocalHandler, local_handler
from fastapi_events.middleware import EventHandlerASGIMiddleware
from fastapi_events.typing import Event
from loguru import logger

from ..interface import (
    BaseDispatcher,
    BaseEventName,
    BaseEventPayload,
    EventHandlerFunc,
)

MIDDLEWARE_ID: int = 324684154273


class FastAPIEventsDispatcher(BaseDispatcher):
    def __init__(self, event_handler: LocalHandler = local_handler):
        self._event_handler = event_handler

    def init_fastapi_app(self, app):
        app.add_middleware(
            EventHandlerASGIMiddleware,
            handlers=[self._event_handler],
            middleware_id=MIDDLEWARE_ID,
        )

    async def dispatch(self, payload: BaseEventPayload, background: bool = True):
        if not background:
            logger.warning(
                "FastAPIEventsDispatcher does not support foreground dispatching."
            )
            return

        dispatch(payload.event_name.fqn(), payload=payload, middleware_id=MIDDLEWARE_ID)

    def register_handler(self, *events: BaseEventName):
        def decorator(func: EventHandlerFunc):
            handler = self.wrap_handler(func)

            async def wrapper(evt: Event):
                try:
                    await handler(
                        event_name=BaseEventName.from_fqn(evt[0]), payload=evt[1]
                    )
                except Exception as e:
                    logger.exception(f"Error handling event {evt[0]}: {e}")

            for event in events:
                self._event_handler.register(wrapper, event_name=event.fqn())
            return func

        return decorator
