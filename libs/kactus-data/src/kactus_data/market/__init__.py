"""Market read models over the OLAP (DuckDB) tables.

The write side of these tables is ``kactus_data.sources.*`` and
``kactus_data.portfolio.provider``; this subpackage is the read side. It lives
in kactus-data rather than in the data-plane service because DuckDB access is
this library's job — the service is only the HTTP skin over it.
"""
