# VNStock Data Pipeline — TODO

## ✅ Completed

- [x] VNStock API documentation (split into 6 files)
- [x] `VnstockSource` base class (parallel to `HttpDataSource`)
- [x] DuckDB table schemas: `stock_ohlcv`, `stock_listing`, `stock_company`, `stock_finance`
- [x] OHLCV source (`VnstockOHLCVSource`) — all intervals
- [x] Listing source (`VnstockListingSource`)
- [x] Company source (`VnstockCompanySource`)
- [x] Finance source (`VnstockFinanceSource`) — 4 report types
- [x] CLI commands: `python manage.py data stock {ohlcv,listing,company,finance}`
- [x] `DataSourceProtocol` in `pipeline.py` — supports both `HttpDataSource` and `VnstockSource`
- [x] Unit tests with mocked vnstock library

## 🔲 Future Work

### Scheduling (Airflow/Celery)

> Current pipeline code is **already compatible** with Airflow/Celery — just call `SyncPipeline.run()` from a task definition.

- [ ] Create Airflow DAGs in `kactus_data/jobs/stock_daily.py`
- [ ] Create Celery task definitions in `kactus_data/jobs/stock_tasks.py`
- [ ] Implement daily cron: OHLCV at 16:00 VNT (Mon-Fri)
- [ ] Implement hourly cron: OHLCV at 09:00-15:00 VNT (Mon-Fri)
- [ ] Implement weekly cron: Weekly candles + news (Saturday 09:00)
- [ ] Implement monthly cron: Monthly candles + financials + ownership (1st of month)

### Multi-Symbol Batch Sync

- [ ] CLI command: `python manage.py data stock ohlcv-all --interval 1D`
- [ ] Rate-limiting loop (respect 60 req/min for Free tier)
- [ ] Parallel workers with `ThreadPoolExecutor` (max 3)
- [ ] Progress bar with completion stats

### Incremental Updates

- [ ] Track last sync date per symbol in DuckDB metadata table
- [ ] Only fetch new data since last sync (avoid full re-fetch)
- [ ] CLI flag: `--incremental` / `--full`

### Real-Time Polling

- [ ] `Trading.price_board()` polling source
- [ ] `Quote.intraday()` tick-by-tick source
- [ ] Long-running poller process with configurable interval

### Additional Data

- [ ] International data source (Forex, Crypto via MSN)
- [ ] Shareholders and insider deals
- [ ] Corporate events calendar
