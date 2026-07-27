"""Gold domain constants — settings entity type, queue job types, read caps."""

from __future__ import annotations

from enum import StrEnum

#: The ``global_settings.entity_type`` for a gold series' availability schedule.
#: A plain string, not an enum member: the registry is str-keyed, and the enum
#: it came from lived in kactus-common where domain values may not.
GOLD_AVAILABILITY_SCHEDULE = "gold_availability_schedule"

# Gold history gets its own read cap: the XAU series alone is ~6.5k daily
# points, so the generic OLAP MAX_LIMIT would silently truncate a "Max" range.
DEFAULT_GOLD_HISTORY_LIMIT = 2500
GOLD_HISTORY_MAX_LIMIT = 10_000


class GoldJobType(StrEnum):
    """The gold jobs that run on the shared sync-job queue.

    Values are the ``sync_jobs.job_type`` wire/DB strings, unchanged from the
    retired ``SyncJobType`` — stored and queued jobs keep working.
    """

    GOLD_BACKFILL = "gold_backfill"
    GOLD_SYNC = "gold_sync"
