"""kactus-data — Data ETL library.

Provides data sources, storage adapters, and sync pipelines
for use standalone, in Airflow DAGs, or Celery tasks.
"""

# ORM model modules in this package — used by load_models() for Alembic autogenerate
MODELS: list[str] = []
