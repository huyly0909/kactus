"""Composite dispatcher — combines blinker (sync) and fastapi-events (background)."""

from loguru import logger

from ..interface import (
    BaseDispatcher,
    BaseEventName,
    BaseEventPayload,
    EventHandlerFunc,
)
from .blinker import BlinkerDispatcher
from .fastapi_events import FastAPIEventsDispatcher


class CompositeDispatcher(BaseDispatcher):
    """Dispatches events to the appropriate backend automatically.

    - Background: uses FastAPIEventsDispatcher
    - Foreground: uses BlinkerDispatcher
    """

    def __init__(self):
        self.blinker_dispatcher = BlinkerDispatcher()
        self.fastapi_events_dispatcher = FastAPIEventsDispatcher()

    def init_fastapi_app(self, app):
        self.fastapi_events_dispatcher.init_fastapi_app(app)

    async def dispatch(self, payload: BaseEventPayload, background: bool = True):
        if background:
            await self.fastapi_events_dispatcher.dispatch(payload, background=True)
        else:
            await self.blinker_dispatcher.dispatch(payload, background=False)

    def register_handler(self, *events: BaseEventName):
        def decorator(func: EventHandlerFunc):
            _ = self.blinker_dispatcher.register_handler(*events)(func)
            fe_rv = self.fastapi_events_dispatcher.register_handler(*events)(func)
            logger.debug(f"Registered handler for events: {events}")
            return fe_rv

        return decorator
