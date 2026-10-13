"""Shared sync-job queue — durable FIFO orchestration for DuckDB writes.

DuckDB permits a single writer, so the data plane runs one dispatcher that
claims queued jobs one at a time. This package owns the cross-service pieces:
the ``SyncJob`` ORM model (Postgres), its enums, read schema, and the
``SyncJobService`` lifecycle used by both the enqueuer (kactus-fin) and the
dispatcher (kactus-data-plane). Gold is the first consumer; stock crawls
migrate onto the queue later.
"""
