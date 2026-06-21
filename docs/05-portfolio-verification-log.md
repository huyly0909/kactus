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
decision-support (`news`/`events`/`ratios`) lúc đó hỏng trên vnstock 3.4.2 — đã nâng vnstock
4.x; nhưng **re-verify thật (2026-06-20, xem §1.1) phát hiện chúng vẫn chưa chạy đúng trong
cấu hình prod** và đã fix dứt điểm. `foreign_trade` vẫn không khả dụng (đã gỡ).

## 1.1 Live re-verify (2026-06-20) — key thật, full ETL path

Smoke trước (và phiên fix #1) chỉ dùng `StockMarketSource()` **mặc định = VCI**, nhưng provider
thật chạy bằng `settings.data_source = **KBS**`. Test thật với key Community + full path
provider→DuckDB→read-back lộ ra 2 bug unit test (FakeMarket) không bắt được:

| Kind | KBS (prod cũ) | VCI | Vấn đề |
|---|---|---|---|
| news | 1 row | 50 row | KBS gần như rỗng |
| events | 0 row | 50 row | KBS rỗng hoàn toàn |
| ratios | crash | crash | PK `(symbol, period)` đụng — xem dưới |

- **Bug A — sai nguồn:** `news`/`events` gần như rỗng trên KBS. **Fix:** định tuyến
  `news`/`events`/`ratios` qua **VCI** (`decision_market` riêng trong `StockAssetProvider`,
  `build_providers(decision_source="VCI")`); `quotes`/`catalog` giữ nguồn settings (KBS).
- **Bug B — ratios crash:** vnstock 4.x trả frame ratio **chuyển vị** (metric là dòng, quý
  `2025-Q1` là cột) → normalizer cũ gán mọi dòng `period="quarter"` → đụng PK → cả crawl
  ratios chết. **Fix:** `market.ratios()` pivot lại — mỗi cột-quý thành 1 dòng
  `(symbol, period=<quý>)`, `raw_json` = map `{metric: value}` của quý đó (fallback giữ
  one-row-per-record nếu frame đã dạng tidy). `_is_period_col` nhận diện cột-kỳ qua regex năm.

**Kết quả re-verify (prod-shaped: quotes/catalog=KBS, decision=VCI):**

| Kind | stored | read | ghi chú |
|---|---|---|---|
| quotes | 2 | 2 | FPT 72.300 / VCB 62.300 ✅ |
| news | **100** | 100 | 50/mã ✅ |
| events | **100** | 100 | 50/mã ✅ |
| ratios | **8** | 8 | 4 quý/mã (`2018-Q1..Q4`), PK unique, **không crash** ✅ |

Tests: **285/285 pass** (thêm `test_ratios_transposed_frame_pivots_per_quarter`,
`test_decision_kinds_use_decision_market`; fixtures cập nhật cho `decision_market`).

## 2. Issues — trạng thái

### ✅ Đã xử lý (2026-06-18; #1c + ratios fix bổ sung 2026-06-20)

| # | Vấn đề | Cách đã fix |
|---|---|---|
| 1 | **vnstock 3.4.2: `news`/`events`/`ratios` raise `KeyError 'data'`** (TCBS chết). | **Nâng `vnstock` 3.4.2 → 4.0.4** (Unified UI, gỡ TCBS, phục vụ qua VCI). API surface tương thích — `Trading`/`Company`/`Finance`/`Quote`/`Listing` + method names không đổi, **không phải re-wire seam**. ⚠️ **Nâng thôi CHƯA đủ** — re-verify thật (§1.1, 2026-06-20) lộ ra `news`/`events` gần như rỗng trên nguồn prod **KBS** và `ratios` crash PK; đã fix bằng **định tuyến decision-support qua VCI** + **pivot ratios**. Live (prod-shaped): news=100, events=100, ratios=8, quotes=2 ✅. 4.x trả `price_board` **MultiIndex columns** → `_flatten_columns` + `_pick` vẫn bóc đúng. |
| 1c | **`news`/`events` rỗng trên nguồn prod KBS; `ratios` crash PK do frame chuyển vị** (chỉ lộ khi test full ETL với key thật — FakeMarket che mất). | **Nguồn:** `StockAssetProvider` thêm `decision_market` riêng (mặc định **VCI**) cho `news`/`events`/`ratios`; `quotes`/`catalog` giữ `settings.data_source`. **ratios:** `market.ratios()` pivot frame chuyển vị (metric=dòng, quý=cột) → 1 dòng/`(symbol, quý)`, `raw_json`={metric:value}; fallback tidy giữ nguyên. Chi tiết + số liệu live ở §1.1. |
| 1b | **`foreign_trade` raise `NotImplementedError`** (chỉ TCBS có). | **VCI 4.x vẫn không hỗ trợ** (smoke: `RetryError[NotImplementedError]`). → **Gỡ khỏi đường crawl**: bỏ `FOREIGN_TRADE` khỏi `StockAssetProvider._kind_table`/fetch map + job `crawl_foreign_trade` trong scheduler (giờ **6 job**, trừ catalog). Enum `CrawlKind.FOREIGN_TRADE` + `STOCK_FOREIGN_TRADE_TABLE` + `market.foreign_trade()` giữ **dormant** để bật lại nếu có nguồn. `supported_kinds()` không còn quảng cáo nó. |
| 2 | **`fin user create-admin` crash `"No settings registered"`**. | Thêm `@cli.callback() _bootstrap()` gọi `get_settings()` vào `kactus_fin/cli/user.py` (giống `cli/server.py`). Áp cho cả `create`/`create-admin`/`list`/`reset_password`. Smoke: lệnh đã qua phần settings, chỉ dừng ở Postgres chưa chạy (connection refused) — không còn `"No settings registered"`. |
| 3 | **Tier không nhận diện → concurrency=1**. | `auth.py`: thêm tier `"community": 60`; set cờ `_AUTHENTICATED` khi `setup_api_key` thành công; `vnstock_max_concurrency()` khi tier vô danh **nhưng đã auth** → giả định 60rpm (→ concurrency **3**) thay vì guest=1. Không key → vẫn guest=1 (an toàn). Có unit test. |

> ✅ **Đã re-verify live với key thật (Community)** trong cấu hình prod-shaped — xem §1.1.
> Decision-support kinds giờ trả dữ liệu thật qua VCI; full E2E qua Postgres + SSE vẫn nên
> chạy lại 1 lần theo §4 + 04 §16 trước khi tin tưởng tuyệt đối.

## 3. Deps (2026-06-18)

- Per-package: `apscheduler`/`pytz`/`vnstock` → **kactus-data**; `sse-starlette` + `kactus-data`
  (workspace) → **kactus-fin**; root `pyproject` chỉ còn `pytest`.
- **vnstock `>=4.0.4`** (vnai 2.4.9, vnstock-ezchart 1.0.2). vnstock 4.x kéo `pandas<3`
  (qua vnstock-ezchart) → **đã hạ pin `pandas` từ `>=3.0.1` xuống `>=2.2,<3`** ở **kactus-common**
  + **kactus-data** (resolved 2.3.3). Không dùng feature pandas-3 nên không ảnh hưởng code.
- `uv sync --all-packages` sạch, **285/285 unit test pass**.

## 4. Re-verify nhanh

Xem [04 §16 "Cách chạy / verify"](04-portfolio-feature.md). Cốt lõi: dựng Postgres,
`fin db upgrade`, `sync-catalog`, rồi `crawl --kind quotes` hoặc E2E curl
login→create→add→refresh→quotes. Smoke nhanh nhất (không cần DB): từ `packages/kactus-data`
gọi `init_vnstock_auth()` + `StockMarketSource().price_board(["FPT","VCB"])`.

> ⚠️ **Nguồn quan trọng khi verify decision-support:** `news`/`events`/`ratios` chỉ giàu dữ
> liệu trên **VCI**, gần như rỗng trên **KBS**. Dùng đúng đường prod là `build_providers(...)`
> (đã tự route decision-support qua `decision_market="VCI"`) — **đừng** test bằng
> `StockMarketSource()` mặc định rồi tưởng prod (chạy KBS) cũng vậy. Đó chính là cái bẫy đã
> khiến #1 bị tưởng nhầm là xong (xem §1.1).
