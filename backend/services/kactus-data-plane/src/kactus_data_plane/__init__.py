"""Kactus data plane — the only process that opens DuckDB read-write.

Owns the ETL: the DuckDB storage handle, the ``AssetProvider`` registry, the
APScheduler cron jobs and the vnstock session. Serves them to the control plane
over ``/internal/*``, which is reachable on the internal network only.

Runs at **one worker, one replica** — permanently. That is not a limitation
waiting to be lifted, it is the reason this service exists: DuckDB permits one
read-write process or several read-only ones, never both across processes, and
the scheduler must fire each cron job exactly once. Isolating that constraint
into a small ETL service is what lets kactus-fin scale out freely.

No Alembic here on purpose. It shares kactus-fin's Postgres database and its
migration head; a second migration lineage over one database is how you get two
heads and a stuck deploy.
"""

# ORM model modules in this package — none: every table it touches is defined
# upstream (kactus_common.portfolio.model) or lives in DuckDB.
MODELS: list[str] = []
