# API Reference

> Complete specification of all VNStock API classes, methods, parameters, and return types.

---

## API Summary

| API Class | Method | Data Type | Collection Frequency | Auth Required |
|-----------|--------|-----------|----------------------|---------------|
| `Listing` | `all_symbols()` | All listed stocks | On-demand | ❌ |
| `Listing` | `symbols_by_exchange()` | Stocks by exchange | On-demand | ❌ |
| `Listing` | `symbols_by_group()` | Stocks by group | On-demand | ❌ |
| `Listing` | `symbols_by_industry()` | ICB classification | On-demand | ❌ (VCI only) |
| `Listing` | `all_indices()` | Market indices | On-demand | ❌ |
| `Listing` | `indices_by_group()` | Indices by group | On-demand | ❌ |
| `Quote` | `history()` | OHLCV candlestick | 1m → 1M intervals | ❌ |
| `Quote` | `intraday()` | Tick-by-tick trades | Real-time (polling) | ❌ |
| `Trading` | `price_board()` | Live market board | Real-time (polling) | ❌ |
| `Finance` | `income_statement()` | Income / P&L | Quarterly / Yearly | ❌ |
| `Finance` | `balance_sheet()` | Balance sheet | Quarterly / Yearly | ❌ |
| `Finance` | `cash_flow()` | Cash flow statement | Quarterly / Yearly | ❌ |
| `Finance` | `ratio()` | Financial ratios | Quarterly / Yearly | ❌ |
| `Company` | Various methods | Company info | On-demand | ❌ |
| `Trade` | `login()` / `place_order()` | Order execution | Real-time | ✅ JWT + OTP |
| `Vnstock` | `fx()` / `crypto()` | International data | Daily only | ❌ |

---

## 1. `Listing` — Stock Listing Info

Get all listed stock symbols and their classifications.

### Constructor

```python
from vnstock import Listing

listing = Listing(source='KBS')  # or 'VCI'
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | `str` | Yes | Data source: `'KBS'` or `'VCI'` |

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `listing.all_symbols()` | All listed symbols | DataFrame: `symbol`, `organ_name` |
| `listing.symbols_by_exchange(exchange)` | Symbols filtered by exchange | DataFrame |
| `listing.symbols_by_group(group)` | Symbols filtered by group | DataFrame |
| `listing.symbols_by_industry()` | ICB industry classification (**VCI only**) | DataFrame |
| `listing.all_indices()` | All market indices | DataFrame |
| `listing.indices_by_group(group)` | Indices filtered by group | DataFrame |

**`symbols_by_exchange` — `exchange` values:** `HOSE`, `HNX`, `UPCOM`

### Example

```python
listing = Listing(source='KBS')

# Get all symbols
all_stocks = listing.all_symbols()
print(f"Total listed stocks: {len(all_stocks)}")

# Filter by exchange
hose_stocks = listing.symbols_by_exchange('HOSE')
```

---

## 2. `Quote` — Historical Price (OHLCV)

Fetch historical candlestick and intraday trade data.

### Constructor

```python
from vnstock import Quote

quote = Quote(symbol='VCI', source='KBS')  # or 'VCI'
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbol` | `str` | Yes | Stock ticker symbol (e.g. `'VCI'`, `'ACB'`) |
| `source` | `str` | Yes | Data source: `'KBS'` or `'VCI'` |

---

### 2.1 `quote.history()` — OHLCV Candlestick Data

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start` | `str` | Yes (if no `length`) | — | Start date in `YYYY-MM-DD` format |
| `end` | `str` | No | Today | End date in `YYYY-MM-DD` format |
| `interval` | `str` | No | `'1D'` | Candlestick time frame |
| `length` | `str` / `int` | No | — | Lookback period or bar count |
| `get_all` | `bool` | No | `False` | Return all columns (KBS only) |

#### Supported Intervals

| Interval | Description | Typical Use Case |
|----------|-------------|------------------|
| `1m` | 1 minute | Intraday micro-analysis |
| `5m` | 5 minutes | Short-term intraday |
| `15m` | 15 minutes | Intraday swing trading |
| `30m` | 30 minutes | Intraday position tracking |
| `1H` | 1 hour | **Hourly cron data collection** |
| `1D` | 1 day | **Daily cron data collection** |
| `1W` | 1 week | Weekly analysis / reporting |
| `1M` | 1 month | Monthly analysis / reporting |

#### Flexible `length` Formats

| Format | Example | Meaning |
|--------|---------|---------|
| Period string | `"1M"`, `"3M"`, `"1Y"` | Month / quarter / year lookback |
| Days (int or str) | `150`, `"150"` | Number of calendar days |
| Bar count | `"100b"`, `"50b"` | Number of candles/bars |

#### Returns

DataFrame with columns:

| Column | Type | Description |
|--------|------|-------------|
| `time` | `datetime` | Candle timestamp |
| `open` | `float` | Opening price |
| `high` | `float` | Highest price |
| `low` | `float` | Lowest price |
| `close` | `float` | Closing price |
| `volume` | `int` | Trading volume |

#### Examples

```python
# Daily OHLCV for last month
quote.history(length="1M", interval="1D")

# Hourly OHLCV for specific date range
quote.history(start='2024-01-01', end='2024-05-25', interval="1H")

# 1-minute bars, last 100 candles
quote.history(length="100b", interval="1m")

# Weekly data for year
quote.history(start='2024-01-01', end='2024-12-31', interval="1W")
```

---

### 2.2 `quote.intraday()` — Trade-by-Trade Data

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_size` | `int` | `100` | Number of records (max ~150,000) |
| `get_all` | `bool` | `False` | Return all columns (KBS only) |
| `last_time` | `str` / `int` | `None` | Time cutoff for pagination (VCI only) |

#### Returns

DataFrame with columns:

| Column | Type | Description |
|--------|------|-------------|
| `time` | `datetime` | Trade timestamp |
| `price` | `float` | Executed price |
| `volume` | `int` | Trade volume |
| `match_type` | `str` | `'Buy'` or `'Sell'` |
| `id` | `int` | Unique trade ID (cursor for deduplication) |

#### Examples

```python
# Get latest 100 intraday trades
quote.intraday(page_size=100)

# Get all trades for a high-liquidity stock
quote.intraday(page_size=150_000)
```

---

## 3. `Trading` — Real-Time Trading Board

Get a live snapshot of the market order book.

### Constructor

```python
from vnstock import Trading

trading = Trading(source="KBS", symbol="VCI")
```

---

### 3.1 `trading.price_board()` — Live Market Snapshot

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbols_list` | `list[str]` | Yes | List of stock symbols to query |

> **Note:** This is the only API method that supports **multiple symbols in a single call**.

#### Returns — KBS Source (29 columns, flat)

| Column Group | Columns |
|--------------|---------|
| **Identity** | `symbol`, `exchange` |
| **Prices** | `reference_price`, `open_price`, `high_price`, `low_price`, `close_price` |
| **Changes** | `price_change`, `percent_change` |
| **Volume** | `total_trades`, `total_value` |
| **Bid** | `bid_price_1`, `bid_price_2`, `bid_price_3`, `bid_vol_1`, `bid_vol_2`, `bid_vol_3` |
| **Ask** | `ask_price_1`, `ask_price_2`, `ask_price_3`, `ask_vol_1`, `ask_vol_2`, `ask_vol_3` |
| **Foreign** | `foreign_buy_volume`, `foreign_sell_volume` |

#### Returns — VCI Source (77 columns, MultiIndex)

| Group | Column Count | Key Columns |
|-------|-------------|-------------|
| **LISTING** | 24 | `symbol`, `ceiling`, `floor`, `ref_price`, `stock_type`, `exchange`, `trading_status`, `listed_share` |
| **MATCH** | 38 | `match_price`, `match_vol`, `accumulated_value`, `foreign_buy`, `foreign_sell`, `ATO_price`, `ATC_price`, `open_interest` |
| **BID_ASK** | 15 | `bid_price_1/2/3`, `ask_price_1/2/3`, volumes per level, `transaction_time` |

#### Example

```python
board = trading.price_board(symbols_list=['VCI', 'VCB', 'ACB'])
```

---

## 4. `Company` — Company Information

Access company overview, leadership, and corporate events.

### Constructor

```python
from vnstock import Vnstock

stock = Vnstock().stock(symbol='ACB', source='VCI')
company = stock.company
```

### Methods

| Method | Description | Source Availability |
|--------|-------------|---------------------|
| `company.overview()` | Company overview | KBS (30 cols) / VCI (10 cols) |
| `company.shareholders()` | Major shareholders | KBS, VCI |
| `company.officers()` | Board of directors & management | KBS, VCI |
| `company.subsidiaries()` | Subsidiaries | **KBS only** |
| `company.affiliates()` | Affiliated companies | KBS, VCI |
| `company.news()` | Company news articles | KBS, VCI |
| `company.events()` | Corporate events calendar | KBS, VCI |
| `company.insider_deals()` | Insider trading records | **KBS only** |
| `company.ownership_structure()` | Ownership breakdown | **KBS only** |

---

## 5. `Finance` — Financial Reports

Access quarterly and yearly financial statements.

### Constructor

```python
from vnstock import Finance

finance = Finance(source="KBS", symbol="VCI")
```

### Methods

| Method | Description | `period` Parameter |
|--------|-------------|---------------------|
| `finance.income_statement(period)` | Income / P&L statement | `'quarter'` or `'year'` |
| `finance.balance_sheet(period)` | Balance sheet | `'quarter'` or `'year'` |
| `finance.cash_flow(period)` | Cash flow statement | `'quarter'` or `'year'` |
| `finance.ratio(period)` | Financial ratios | `'quarter'` or `'year'` |

### Example

```python
finance = Finance(source="KBS", symbol="VCI")

# Quarterly income statement
income_q = finance.income_statement(period='quarter')

# Yearly balance sheet
balance_y = finance.balance_sheet(period='year')
```

---

## 6. `Vnstock` — International Data (MSN Source)

Access Forex, Crypto, and Global Index data. **Daily interval only.**

### Forex

```python
from vnstock import Vnstock

fx = Vnstock().fx(symbol='USDJPY', source='MSN')
fx.quote.history(start='2024-01-01', end='2024-12-31')
```

### Crypto

```python
crypto = Vnstock().crypto(symbol='BTC', source='MSN')
crypto.quote.history(start='2024-01-01', end='2024-12-31')
```

### Global Indices

```python
index = Vnstock().world_index(symbol='DJI', source='MSN')
index.quote.history(start='2024-01-01', end='2024-12-31')
```

> **Important:** International data only supports **daily interval** (`1D`).

---

## 7. Messaging Integration — Alerts

Send alerts via messaging platforms.

### Telegram

```python
from vnstock import Vnstock

bot = Vnstock().bot(token='BOT_TOKEN', chat_id='CHAT_ID')
bot.send_message("Price alert: VCI crossed 35,000")
```

### Other Platforms

- **Slack** — via Webhook integration
- **Lark** — via BotBuilder integration
