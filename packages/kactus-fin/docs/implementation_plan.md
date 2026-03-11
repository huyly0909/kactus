# Admin Data Pages — Company, Finance, Stock

Add three new admin pages for viewing and manually syncing market data from DuckDB.

## Context

Data lives in **DuckDB** tables (not OLTP):

| Table | Primary Keys | Key Columns |
|-------|-------------|-------------|
| `stock_company` | `symbol` | company_name, industry, exchange, market_cap, synced_at |
| `stock_finance` | `symbol + period + year + quarter + report_type` | data_json, source, synced_at |
| `stock_ohlcv` | `symbol + time + interval` | open, high, low, close, volume |
| `stock_listing` | `symbol` | organ_name, source, synced_at |

Currently **no API endpoints** exist for querying DuckDB — only CLI commands. We need to build the full stack: backend API → frontend service → admin pages.

---

## Proposed Changes

### Backend: kactus-fin — 3 Feature Folders

Following the existing `KactusApp` pattern (like `admin/`, `project/`), create **3 separate feature folders** under `src/kactus_fin/`:

---

#### Company Feature — `company/`

##### [NEW] `company/__init__.py`
##### [NEW] `company/app.py`

```python
company_app = KactusApp(name="company", superuser_routes=[router])
```

##### [NEW] `company/api.py`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/company` | List all companies from `stock_company` |
| `GET` | `/api/company/{symbol}` | Company detail (parsed overview_json) |
| `POST` | `/api/company/sync` | Sync company data for a symbol |

##### [NEW] `company/schema.py`

Pydantic response schemas for company list/detail.

##### [NEW] `company/service.py`

Wraps `DuckDBStorage.query()` for reading and [SyncPipeline](file:///Users/recurve/project/test-test/kactus/packages/kactus-data/src/kactus_data/pipeline.py#L35-L170) for sync.

---

#### Finance Feature — `finance/`

##### [NEW] `finance/__init__.py`
##### [NEW] `finance/app.py`

```python
finance_app = KactusApp(name="finance", superuser_routes=[router])
```

##### [NEW] `finance/api.py`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/finance` | List finance records (filter by symbol, report_type) |
| `GET` | `/api/finance/{symbol}` | Finance detail for a symbol |
| `POST` | `/api/finance/sync` | Sync finance data (symbol, report_type, period) |

##### [NEW] `finance/schema.py`

Pydantic response schemas for finance list/detail.

##### [NEW] `finance/service.py`

Wraps DuckDB queries and SyncPipeline for finance data.

---

#### Stock Feature — `stock/`

##### [NEW] `stock/__init__.py`
##### [NEW] `stock/app.py`

```python
stock_app = KactusApp(name="stock", superuser_routes=[router])
```

##### [NEW] `stock/api.py`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/stock` | List from `stock_listing` |
| `GET` | `/api/stock/{symbol}/ohlcv` | OHLCV data for a symbol |
| `POST` | `/api/stock/sync-listing` | Sync all listings |
| `POST` | `/api/stock/sync-ohlcv` | Sync OHLCV (symbol, start, end, interval) |

##### [NEW] `stock/schema.py`

Pydantic response schemas for stock/OHLCV.

##### [NEW] `stock/service.py`

Wraps DuckDB queries and SyncPipeline for stock/OHLCV data.

---

#### [MODIFY] [app.py](file:///Users/recurve/project/test-test/kactus/packages/kactus-fin/src/kactus_fin/app.py)

Register 3 new feature apps:

```python
app_manager.register(company_app)
app_manager.register(finance_app)
app_manager.register(stock_app)
```

---

### Frontend: bloom-ui — Data Admin Service

#### [NEW] `bloom-ui/src/services/dataAdminService.ts`

```
dataAdminService = {
  // Company
  getCompanies, getCompanyDetail, syncCompany,
  // Finance
  getFinanceRecords, getFinanceDetail, syncFinance,
  // Stock
  getStocks, getStockOhlcv, syncListing, syncOhlcv,
}
```

#### [MODIFY] [bloom-ui/src/services/index.ts](file:///Users/recurve/project/test-test/kactus-bloom/packages/bloom-ui/src/services/index.ts)

Add `dataAdminService` export.

---

### Frontend: bloom-app — Admin Pages

Follow existing admin page patterns (flat [.tsx](file:///Users/recurve/project/test-test/kactus-bloom/packages/bloom-app/src/App.tsx) files in `pages/Admin/`, `useState`/`useEffect`, Mantine Table).

#### [NEW] `pages/Admin/Companies.tsx`

- Table: symbol, company_name, industry, exchange, market_cap, synced_at
- Click row → detail modal (parsed overview_json)
- Sync button: input symbol → POST sync

#### [NEW] `pages/Admin/Finance.tsx`

- Table: symbol, report_type, period, year, quarter, synced_at
- Filters: symbol, report_type
- Click row → detail modal (parsed data_json)
- Sync button: input symbol, report_type, period → POST sync

#### [NEW] `pages/Admin/Stocks.tsx`

- Table: symbol, organ_name, source, synced_at (from `stock_listing`)
- Click row → OHLCV detail view (mini table or chart preview)
- Sync listing button (sync all)
- Sync OHLCV button: input symbol, date range, interval → POST sync

#### [MODIFY] [pages/Admin/index.tsx](file:///Users/recurve/project/test-test/kactus-bloom/packages/bloom-app/src/pages/Admin/index.tsx)

Add 3 new sidebar items (Company, Finance, Stock) with icons.

#### [MODIFY] [router/index.tsx](file:///Users/recurve/project/test-test/kactus-bloom/packages/bloom-app/src/router/index.tsx)

Add 3 new routes under the admin group:
```
/admin/companies → AdminCompaniesPage
/admin/finance   → AdminFinancePage
/admin/stocks    → AdminStocksPage
```

---

## Verification Plan

### Manual Verification
1. Start kactus-fin dev server (`python manage.py fin dev`)
2. Start bloom dev server (`pnpm dev`)
3. Login as superuser → navigate to Admin
4. Verify new sidebar items appear
5. Test list/detail/sync for each domain
