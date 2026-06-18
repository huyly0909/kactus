# 05 — Portfolio: Verification Log & Known Issues

> Living tracker cho việc **verify live** + **bug đang mở** của tính năng portfolio.
> Bổ sung cho [04-portfolio-feature.md](04-portfolio-feature.md). Unit test xanh **không**
> đủ — chúng dùng `FakeMarket` offline; doc này ghi nhận hành vi với vnstock + key thật.

## 1. Live verification (2026-06-18)

Chạy thật: `postgres:16-alpine` :5432 + `fin db upgrade` + uvicorn (no reload) + key thật
(`KACTUS_VNSTOCK_API_KEY`, tier **Community/60rpm**). Chuỗi E2E qua HTTP đều `code:"0"`:

| Bước | Kết quả |
|---|---|
| Lifespan boot | auth → SSE handler → scheduler (7 jobs) → runtime ✅ |
| `data portfolio crawl --kind quotes FPT,VCB` | DuckDB `stock_price_board` = 2 rows; Postgres `crawl_runs` success ✅ |
| `data portfolio sync-catalog stock` | 1531 mã, FPT/VCB tag VN30/VN100 ✅ |
| login → create portfolio → add `{STOCK,FPT}` | owner_id = admin; add validate qua catalog ✅ |
| `POST /{id}/refresh?kind=quotes` → `GET /{id}/quotes` | giá FPT thật (~2s sau): match 72.300 / ref 73.200 / KL 997.219 ✅ |
| SSE `/stream` | nhận `event: data_refreshed {STOCK,quotes,[FPT],crawl_run_id}` + heartbeat ✅ |

**Kết luận:** đường **quotes + catalog + refresh + SSE** chạy live đúng thiết kế. Các kind
decision-support thì **không** (xem #1 bên dưới).

## 2. Known issues (mở)

| # | Vấn đề | Mức | Trạng thái / cách xử lý |
|---|---|---|---|
| 1 | **vnstock 3.4.2: `news`/`events`/`ratios` raise `KeyError 'data'`, `foreign_trade` raise `NotImplementedError`** (universal: FPT/VNM/HPG). `_per_symbol` nuốt lỗi → âm thầm 0 row trong prod. Gốc: provider **TCBS chết** (gỡ ở 3.5.0, "API no longer accessible từ 15/12/2024") + VCI parse lỗi. | 🔴 High | **Chưa fix.** Đề xuất: spike nâng **vnstock 4.0.4** (Unified UI + stability fixes) rồi re-test đường quotes/OHLCV đang chạy. Trong lúc đó UI nên ẩn/disabled tab news/foreign/ratios. |
| 2 | **`python manage.py fin user create-admin` crash `"No settings registered"`** — CLI `fin user` không gọi `get_settings()`/`register_settings()` (chỉ `fin db` qua Alembic và `fin dev` qua `create_app()` chạy). | 🟡 Med | **Chưa fix.** Thêm bootstrap settings vào callback của `fin user` CLI. Workaround: register fin settings trước `_create_user`. |
| 3 | **Tier không nhận diện**: key resolve về Community/60rpm, `vnai.get_tier_info()` không trả tên tier → `_safe_tier_name()` = None → `vnstock_max_concurrency()` rớt về guest=1 (quá thận trọng). | 🟢 Low | Để vậy (an toàn). Nếu cần throughput: map số/tier theo banner "60 requests/phút". |

## 3. Deps (đã tách per-package — 2026-06-18)

`apscheduler`/`pytz`/`vnstock>=3.4.2` → **kactus-data**; `sse-starlette` + `kactus-data`
(workspace) → **kactus-fin**; root `pyproject` chỉ còn `pytest`. `uv sync --all-packages`
sạch, 280/280 test pass. (Thay cho note §16.8 của doc 04.)

## 4. Re-verify nhanh

Xem [04 §16 "Cách chạy / verify"](04-portfolio-feature.md). Cốt lõi: dựng Postgres,
`fin db upgrade`, `sync-catalog`, rồi `crawl --kind quotes` hoặc E2E curl
login→create→add→refresh→quotes. Smoke nhanh nhất (không cần DB): từ `packages/kactus-data`
gọi `init_vnstock_auth()` + `StockMarketSource().price_board(["FPT","VCB"])`.
