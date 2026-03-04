#!/usr/bin/env python3
"""Import smoke tests — verify all kactus-data modules import correctly."""

import pytest


class TestCoreImports:
    """Verify core kactus-data modules import."""

    def test_import_package(self):
        import kactus_data
        assert kactus_data is not None

    def test_import_schemas(self):
        from kactus_data.schemas import SyncDataResponse, SyncResult
        assert SyncDataResponse is not None

    def test_import_http_source(self):
        from kactus_data.sources.http import HttpDataSource
        assert HttpDataSource is not None

    def test_import_storage(self):
        from kactus_data.storage.duckdb import DuckDBStorage
        assert DuckDBStorage is not None

    def test_import_pipeline(self):
        from kactus_data.pipeline import SyncPipeline, DataSourceProtocol
        assert SyncPipeline is not None

    def test_import_jobs(self):
        import kactus_data.jobs
        assert kactus_data.jobs is not None

    def test_cross_package_import(self):
        from kactus_common.database.duckdb.client import DatabaseClient
        assert DatabaseClient is not None


class TestGoldImports:
    def test_import_gold_mihong(self):
        from kactus_data.sources.gold.mihong import MihongGoldSource
        assert MihongGoldSource is not None


class TestStockImports:
    def test_import_base(self):
        from kactus_data.sources.stock.base import VnstockSource
        assert VnstockSource is not None

    def test_import_vnstock_sources(self):
        from kactus_data.sources.stock.vnstock import VnstockOHLCVSource, VnstockListingSource
        assert VnstockOHLCVSource is not None

    def test_import_stock_package(self):
        from kactus_data.sources.stock import VnstockSource, VnstockOHLCVSource
        assert VnstockSource is not None


class TestCompanyImports:
    def test_import_vnstock_company(self):
        from kactus_data.sources.company.vnstock import VnstockCompanySource
        assert VnstockCompanySource is not None

    def test_import_company_package(self):
        from kactus_data.sources.company import VnstockCompanySource, COMPANY_TABLE
        assert VnstockCompanySource is not None


class TestFinanceImports:
    def test_import_vnstock_finance(self):
        from kactus_data.sources.finance.vnstock import VnstockFinanceSource
        assert VnstockFinanceSource is not None

    def test_import_finance_package(self):
        from kactus_data.sources.finance import VnstockFinanceSource, FINANCE_TABLE
        assert VnstockFinanceSource is not None


class TestDomainPlaceholders:
    def test_import_coin(self):
        import kactus_data.sources.coin
        assert kactus_data.sources.coin is not None
