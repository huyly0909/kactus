"""kactus-gold — the gold domain (availability schedules, sync contracts, schemas).

A **domain lib**, not infrastructure: which weekdays SJC quotes, how far back
Mihong can backfill, what a gold history point looks like — none of that belongs
in kactus-common (``CLAUDE.md``: kactus-common is infrastructure only). It sits
in ``libs/domain/`` *below* the libs layer because both sides of the plane split
import it: kactus-fin (admin API, market forwarder) may not import kactus-data,
and kactus-data (ETL, queue handlers) needs the same contracts — so the shared
gold shapes live here, where both reach them and neither can drift.

* ``const``    — settings entity type, queue job types, history read caps.
* ``schedule`` — data-availability schedule config + per-series defaults
  (importing it registers the schema in the ``global_settings`` registry).
* ``schema``   — market read models (board quote, history point, import result).
* ``sync``     — sync-job request schemas + dedup/backfill-floor builders.

No ORM models: gold rides the shared ``global_settings`` and ``sync_jobs``
tables in kactus-common.
"""

# Register the gold availability-schedule settings schema (side effect: the
# entry-point package importing `kactus_gold` populates SETTINGS_SPECS).
from . import schedule  # noqa: F401

# ORM model modules in this package — used by load_models() for Alembic autogenerate
MODELS: list[str] = []
