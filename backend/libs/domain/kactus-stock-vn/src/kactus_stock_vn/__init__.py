"""kactus-stock-vn — the Vietnam stock-market domain (enums, read schemas).

A **domain lib**, not infrastructure: report kinds, candle intervals and what a
quote row looks like are vnstock-shaped business content, which is why they no
longer sit in kactus-common (``CLAUDE.md``: kactus-common is infrastructure
only). Like ``kactus_gold``, it lives in ``libs/domain/`` below the libs layer:
kactus-fin (market forwarder) may not import kactus-data, and kactus-data (ETL)
needs the same contracts — the shared shapes live here so neither can drift.

* ``const``  — report/period/interval enums + per-endpoint default read limits.
* ``schema`` — market read models (listing, quote, company, candle, news,
  finance report), built by the data plane and re-parsed by the control plane.

No ORM models; the stock tables are OLAP (DuckDB), defined in kactus-data.
"""

# ORM model modules in this package — used by load_models() for Alembic autogenerate
MODELS: list[str] = []
