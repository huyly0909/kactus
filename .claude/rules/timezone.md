# Timezone Convention

All timestamps live in the database as **UTC**. Vietnam-local source values are
kept **verbatim** in their native columns; a derived UTC column carries the
canonical time axis. Display converts UTC → the viewer's timezone.

## The `event_dt` column (OLAP / DuckDB)

`event_dt` is a **reserved column name** on every OLAP business table that has a
time axis. It always means: the **canonical UTC instant** (naive `TIMESTAMP`
holding UTC wall-clock — DuckDB session TZ is pinned to UTC).

- **Every other datetime/date column keeps its native source value** — Vietnam
  local time (`stock_ohlcv.time`, intraday) or a calendar date
  (`gold_price_history.date`, `stock_events.event_date`, string `published_at`).
  The name is the marker: `event_dt` = derived UTC; anything else = native.
- Compute `event_dt` **at ingest**, from the native value, via
  `kactus_data.util.time.to_event_dt` / `to_event_dt_series`
  (VN wall-clock → UTC). Never overwrite the native column.
- Add `event_dt` as the **LAST** column of a `Table` definition — positional
  inserts (`INSERT … SELECT *`) must line up with `ALTER TABLE ADD COLUMN`,
  which appends at the end, on already-created databases.
- **Filter / sync on `event_dt`**, never on a native column — it is the one
  unit-consistent, offset-consistent axis across sources.
- Board/audit-only tables (`gold_price_board`, `stock_price_board`,
  `stock_ratios`) have **no** `event_dt`: their only time axis is the crawl
  stamp, which is already UTC.

## Audit stamps

`crawled_at` / `synced_at` / `imported_at` are written **directly as UTC** via
`kactus_common.datetimes.utcnow_naive()` — no native counterpart. Never
`datetime.now()` (that is server-local).

## OLTP (Postgres)

Already UTC-correct: `DateTimeTzAware` → `TIMESTAMPTZ`, coerces to UTC on both
bind and result; writers use `utcnow()`. Nothing new to do here.

## API

Business timestamps serialize as **`event_dt` only** (UTC, tz-aware `+00:00`)
via `AwareUTCDatetime` (`kactus_common.schemas`). Native VN columns are **not**
returned to the client. Audit stamps also serialize as `AwareUTCDatetime`.

## Display (frontend)

Convert the UTC value to the user's timezone — `useFormatDateTime()` /
`useFormatDate()` read `authStore.user.timezone` (default `Asia/Ho_Chi_Minh`).
Picking **UTC+7** renders correct Vietnam wall-clock; picking **UTC** renders
UTC. Never `new Date(x).toLocaleString()` (that is the browser's zone) or
`fmtDateTime` from `@/lib/format` for a business/audit timestamp.

## labenry-lab

Research/backfill scripts stay **raw VN source** — their CSVs are the truth in
Vietnam local time. Do **not** convert them to UTC; `event_dt` is computed at
the import boundary (`kactus_data/sources/gold/history.py`).

## Backfill

`python manage.py data tz backfill --confirm` populates `event_dt` from the
untouched native columns (**idempotent** — re-runnable). Shifting historical
audit stamps is opt-in and **not** idempotent (`--shift-audit --server-offset N`).
