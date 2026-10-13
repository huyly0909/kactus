"""The queue consumer — one per kactus-fin worker.

**Why here and not in the data plane.**  The plan put this in kactus-data-plane
on the grounds that it was already a single-replica background service.  That
premise dissolved once Phase 1 and 2 landed:

- A Redis consumer *group* wants several consumers, not one.  Each worker
  registers under its own ``consumer_name``, entries are distributed rather than
  duplicated, and a worker dying leaves its pending entries claimable by the
  rest.  Single-replica is the weaker arrangement here, not the stronger one.
- kactus-data-plane deliberately does not depend on kactus-notification
  (see ``deploy/Dockerfile.data-plane``).  Wiring the consumer there would drag
  ``zlapi`` — unofficial, reverse-engineered, ``os.kill``-happy enough to need a
  guard — into the ETL image.  That is exactly the leak Phase 0.6 removed from
  kactus-common, moved rather than fixed.
- The sender, the channel rows and ``NotificationLog`` already live in this
  process.  Nothing has to cross a service boundary.

Either way there is no fourth service, which is the constraint that mattered.
"""

from __future__ import annotations

import os

from kactus_common.database.oltp.session import get_db
from kactus_common.exceptions import ExternalServiceError
from kactus_notification.dispatcher import Notifier
from kactus_notification.model import NotificationChannel
from kactus_notification.queue import NotificationQueueConsumer, QueuedNotification
from kactus_notification.service import NotificationChannelService
from loguru import logger

_consumer: NotificationQueueConsumer | None = None


async def deliver(queued: QueuedNotification) -> None:
    """Send one queued event.

    Raising means *unhandled* and leaves the entry pending for replay, so every
    outcome that is genuinely final returns instead:

    - channel gone or re-owned → return.  Redelivering cannot make it exist.
    - ``ExternalServiceError`` → return.  ``send_event`` already exhausted its
      bounded retry and wrote a FAILED ``NotificationLog``; replaying the stream
      entry would re-run that same retry loop for as long as the channel stays
      broken.

    What *does* propagate is the database being down or a bug in here — the
    cases where trying again later is exactly right.
    """
    async with get_db().get_session() as session:
        channel = await NotificationChannel.get(session, queued.channel_id)
        if channel is None or channel.owner_id != queued.owner_id:
            # Ownership is re-checked here, not trusted from the enqueue: the
            # entry may be handled minutes later, in another process, long after
            # the request that produced it is gone.
            logger.warning(
                f"Dropping queued notification {queued.message_id}: channel "
                f"{queued.channel_id} is missing or no longer owned by "
                f"{queued.owner_id}"
            )
            return

        try:
            await Notifier.send_event(
                session, channel, queued.event, trigger=queued.trigger
            )
        except ExternalServiceError as exc:
            logger.warning(
                f"Queued notification {queued.message_id} failed permanently "
                f"on channel {channel.id}: {exc}"
            )
            return

        await NotificationChannelService.mark_used(session, channel)


def _consumer_name() -> str:
    """Unique per worker process — the group keys pending entries on it."""
    return f"{os.uname().nodename}-{os.getpid()}"


async def start_consumer() -> None:
    """Start this worker's consumer. Called from the app lifespan."""
    global _consumer
    if _consumer is not None:
        return
    _consumer = NotificationQueueConsumer(deliver, consumer_name=_consumer_name())
    await _consumer.start()


async def stop_consumer() -> None:
    """Stop this worker's consumer. Called from the app lifespan."""
    global _consumer
    if _consumer is None:
        return
    await _consumer.stop()
    _consumer = None
