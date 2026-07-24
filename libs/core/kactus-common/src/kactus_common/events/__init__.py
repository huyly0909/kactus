"""Event dispatching system — background tasks and synchronous handlers.

Usage::

    from kactus_common.events import dispatch_event, register_handler
"""

from .backends.composite import CompositeDispatcher
from .interface import BaseEventName, BaseEventPayload

# Default composite dispatcher
dispatcher = CompositeDispatcher()
dispatch_event = dispatcher.dispatch
register_handler = dispatcher.register_handler


# Patch BaseEventPayload to use the default dispatcher
async def _dispatch(self: BaseEventPayload, background: bool = False):
    await dispatch_event(self, background=background)


BaseEventPayload.dispatch = _dispatch

__all__ = [
    "CompositeDispatcher",
    "BaseEventName",
    "BaseEventPayload",
    "dispatcher",
    "dispatch_event",
    "register_handler",
]
