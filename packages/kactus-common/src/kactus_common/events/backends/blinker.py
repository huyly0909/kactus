"""Blinker-based synchronous event dispatcher."""

from blinker import NamedSignal, Namespace
from loguru import logger

from ..interface import (
    BaseDispatcher,
    BaseEventName,
    BaseEventPayload,
    EventHandlerFunc,
)

signals = Namespace()


class BlinkerDispatcher(BaseDispatcher):
    def __init__(self):
        self.signals: dict[BaseEventName, NamedSignal] = {}

    async def dispatch(self, payload: BaseEventPayload, background: bool = False):
        if background:
            logger.warning("BlinkerDispatcher does not support background dispatching.")
            return

        signal = self.signals[payload.event_name]
        await signal.send_async(None, event_name=payload.event_name, payload=payload)

    def register_handler(self, *events: BaseEventName):
        def decorator(func: EventHandlerFunc):
            handler = self.wrap_handler(func)
            for event in events:
                if event not in self.signals:
                    self.signals[event] = signals.signal(event.fqn())
                self.signals[event].connect(handler, weak=False)

            return func

        return decorator

    @staticmethod
    def wrap_handler(func: EventHandlerFunc):
        async def wrapper(_, event_name: BaseEventName, payload: BaseEventPayload):
            await BaseDispatcher._handle(func, event_name, payload)

        return wrapper
