# Data Collection & Cron Jobs

> Scheduling strategies for automated VNStock data collection — hourly, daily, weekly, and monthly.

---

## Vietnam Stock Market Hours

| Session | Time (VNT) | Notes |
|---------|------------|-------|
| **Pre-open (ATO)** | 09:00 – 09:15 | Opening auction |
| **Morning session** | 09:15 – 11:30 | Continuous matching |
| **Lunch break** | 11:30 – 13:00 | No trading |
| **Afternoon session** | 13:00 – 14:30 | Continuous matching |
| **Close (ATC)** | 14:30 – 14:45 | Closing auction |
| **Post-close** | 14:45 – 15:00 | Put-through trades |

**Trading days:** Monday – Friday (excluding Vietnamese public holidays)

---

## Rate Limit Planning

| Tier | Rate Limit | Max Symbols per Cycle | Recommended Sleep |
|------|------------|-----------------------|-------------------|
| **Anonymous** | 20 req/min | ~20 symbols/min | `3s` between requests |
| **Free** | 60 req/min | ~60 symbols/min | `1s` between requests |
| **Insider** | 180–500 req/min | ~180–500 symbols/min | `0.2–0.3s` between requests |

---

## 1. Hourly Collection

**Purpose:** Capture hourly OHLCV candles during market hours for intraday analysis.

### Cron Schedule

```bash
# Run every hour from 09:00 to 15:00, Monday–Friday
0 9-15 * * 1-5 /usr/bin/python3 /path/to/hourly_collect.py
```

| Field | Value | Description |
|-------|-------|-------------|
| Minute | `0` | At the top of each hour |
| Hour | `9-15` | Market hours (9 AM – 3 PM VNT) |
| Day of month | `*` | Every day |
| Month | `*` | Every month |
| Day of week | `1-5` | Monday through Friday |

### Script Example

```python
from vnstock import Quote
from datetime import date

TRACKED_SYMBOLS = ['VCI', 'VCB', 'ACB', 'FPT', 'MWG']

def hourly_collect():
    today = date.today().strftime('%Y-%m-%d')

    for symbol in TRACKED_SYMBOLS:
        quote = Quote(symbol=symbol, source='KBS')
        df = quote.history(length="1D", interval="1H")
        
        # Store latest hourly candle
        if not df.empty:
            latest = df.iloc[-1]
            save_to_storage(symbol, latest, interval='1H')
        
        time.sleep(1)  # Rate limiting

hourly_collect()
```

### What Gets Collected

| Data | Interval | Columns |
|------|----------|---------|
| OHLCV | `1H` | `time`, `open`, `high`, `low`, `close`, `volume` |

**Expected output:** ~7 candles per stock per day (09:00, 10:00, ..., 15:00)

---

## 2. Daily Collection

**Purpose:** Capture end-of-day OHLCV, financial data, and company information after market close.

### Cron Schedule

```bash
# Run at 16:00 (4 PM VNT), Monday–Friday — 1 hour after market close
0 16 * * 1-5 /usr/bin/python3 /path/to/daily_collect.py
```

| Field | Value | Description |
|-------|-------|-------------|
| Minute | `0` | At the top of the hour |
| Hour | `16` | 4 PM VNT (1 hour after close) |
| Day of month | `*` | Every day |
| Month | `*` | Every month |
| Day of week | `1-5` | Monday through Friday |

### Script Example

```python
from vnstock import Quote, Finance, Listing
from datetime import date
import time

def daily_collect():
    today = date.today().strftime('%Y-%m-%d')
    listing = Listing(source='KBS')
    all_symbols = listing.all_symbols()['symbol'].tolist()

    for symbol in all_symbols:
        try:
            # Daily OHLCV
            quote = Quote(symbol=symbol, source='KBS')
            df = quote.history(start=today, end=today, interval="1D")
            save_ohlcv(symbol, df)

            # Financial data (less frequent, but checked daily for updates)
            finance = Finance(source="KBS", symbol=symbol)
            income = finance.income_statement(period='quarter')
            save_financials(symbol, income)

        except Exception as e:
            log_error(symbol, e)

        time.sleep(1)  # Rate limiting (60 req/min for Free tier)

daily_collect()
```

### What Gets Collected

| Data | Method | Frequency |
|------|--------|-----------|
| Daily OHLCV | `Quote.history(interval='1D')` | Every trading day |
| Income Statement | `Finance.income_statement()` | Check daily, updates quarterly |
| Balance Sheet | `Finance.balance_sheet()` | Check daily, updates quarterly |
| Cash Flow | `Finance.cash_flow()` | Check daily, updates quarterly |
| Financial Ratios | `Finance.ratio()` | Check daily, updates quarterly |

---

## 3. Weekly Collection

**Purpose:** Aggregate weekly summaries, run weekly analysis, and generate weekly OHLCV candles.

### Cron Schedule

```bash
# Run every Saturday at 09:00 VNT (after the trading week ends Friday)
0 9 * * 6 /usr/bin/python3 /path/to/weekly_collect.py
```

| Field | Value | Description |
|-------|-------|-------------|
| Minute | `0` | At the top of the hour |
| Hour | `9` | 9 AM VNT |
| Day of month | `*` | Every day |
| Month | `*` | Every month |
| Day of week | `6` | Saturday |

### Script Example

```python
from vnstock import Quote, Listing, Company
from datetime import date, timedelta

def weekly_collect():
    listing = Listing(source='KBS')
    all_symbols = listing.all_symbols()['symbol'].tolist()
    
    end_date = date.today().strftime('%Y-%m-%d')  # Saturday
    start_date = (date.today() - timedelta(days=7)).strftime('%Y-%m-%d')  # Previous Saturday

    for symbol in all_symbols:
        try:
            quote = Quote(symbol=symbol, source='KBS')

            # Weekly OHLCV candle
            df_weekly = quote.history(
                start=start_date,
                end=end_date,
                interval="1W"
            )
            save_weekly_ohlcv(symbol, df_weekly)

            # Company news for the week
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            news = stock.company.news()
            save_company_news(symbol, news)

        except Exception as e:
            log_error(symbol, e)

        time.sleep(1)

weekly_collect()
```

### What Gets Collected

| Data | Method | Notes |
|------|--------|-------|
| Weekly OHLCV | `Quote.history(interval='1W')` | One candle per week per symbol |
| Company News | `Company.news()` | Latest news articles |
| Corporate Events | `Company.events()` | Upcoming dividends, AGM, etc. |
| Insider Deals | `Company.insider_deals()` | KBS only |

---

## 4. Monthly Collection

**Purpose:** Generate monthly reports, capture monthly OHLCV candles, and snapshot ownership/shareholder data.

### Cron Schedule

```bash
# Run on the 1st of every month at 09:00 VNT
0 9 1 * * /usr/bin/python3 /path/to/monthly_collect.py
```

| Field | Value | Description |
|-------|-------|-------------|
| Minute | `0` | At the top of the hour |
| Hour | `9` | 9 AM VNT |
| Day of month | `1` | First day of the month |
| Month | `*` | Every month |
| Day of week | `*` | Any day |

### Script Example

```python
from vnstock import Quote, Finance, Listing, Vnstock
from datetime import date, timedelta

def monthly_collect():
    listing = Listing(source='KBS')
    all_symbols = listing.all_symbols()['symbol'].tolist()

    today = date.today()
    # Previous month range
    first_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_of_last_month = today.replace(day=1) - timedelta(days=1)

    start = first_of_last_month.strftime('%Y-%m-%d')
    end = last_of_last_month.strftime('%Y-%m-%d')

    for symbol in all_symbols:
        try:
            quote = Quote(symbol=symbol, source='KBS')

            # Monthly OHLCV candle
            df_monthly = quote.history(start=start, end=end, interval="1M")
            save_monthly_ohlcv(symbol, df_monthly)

            # Quarterly financials (check for new releases)
            finance = Finance(source="KBS", symbol=symbol)
            income = finance.income_statement(period='quarter')
            balance = finance.balance_sheet(period='quarter')
            cashflow = finance.cash_flow(period='quarter')
            ratios = finance.ratio(period='quarter')
            save_financials(symbol, income, balance, cashflow, ratios)

            # Ownership snapshot
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            shareholders = stock.company.shareholders()
            ownership = stock.company.ownership_structure()
            save_ownership(symbol, shareholders, ownership)

        except Exception as e:
            log_error(symbol, e)

        time.sleep(1)

monthly_collect()
```

### What Gets Collected

| Data | Method | Notes |
|------|--------|-------|
| Monthly OHLCV | `Quote.history(interval='1M')` | One candle per month per symbol |
| Financial Statements | `Finance.*()` | Quarterly/yearly — check for new filings |
| Financial Ratios | `Finance.ratio()` | Latest computed ratios |
| Shareholders | `Company.shareholders()` | Major shareholder snapshot |
| Ownership Structure | `Company.ownership_structure()` | KBS only |
| Subsidiaries | `Company.subsidiaries()` | KBS only |

---

## 5. Near Real-Time Polling

**Purpose:** Live market monitoring during trading hours.

> ⚠️ VNStock does **NOT** support WebSocket/streaming. All "real-time" data is via HTTP polling.

### Option A: `price_board()` Polling (Recommended)

```python
import time
from vnstock import Trading

trading = Trading(source="KBS", symbol="VCI")

# Poll every 5 seconds during market hours
while is_market_open():
    board = trading.price_board(symbols_list=['VCI', 'VCB', 'ACB'])
    process_and_store(board)
    time.sleep(5)  # 12 req/min — well within limits
```

### Option B: `intraday()` Tick-by-Tick Polling

```python
from vnstock import Quote

quote = Quote(symbol='VCI', source='VCI')
last_id = None

while is_market_open():
    trades = quote.intraday(page_size=100)
    new_trades = trades[trades['id'] > last_id] if last_id else trades
    if not new_trades.empty:
        last_id = new_trades['id'].iloc[0]
        store_trades(new_trades)
    time.sleep(3)
```

### Option C: Sub-Minute OHLCV

```python
quote = Quote(symbol='VCI', source='KBS')
df = quote.history(length="50b", interval="1m")
```

---

## 6. Complete Cron Schedule Summary

```bash
# ┌─────── minute (0-59)
# │ ┌───── hour (0-23)
# │ │ ┌─── day of month (1-31)
# │ │ │ ┌─ month (1-12)
# │ │ │ │ ┌ day of week (0=Sun, 1=Mon, ..., 6=Sat)
# │ │ │ │ │
# * * * * * command

# ── HOURLY ──────────────────────────────────────────────
  0 9-15 * * 1-5   /usr/bin/python3 /path/to/hourly_collect.py

# ── DAILY ───────────────────────────────────────────────
  0 16   * * 1-5   /usr/bin/python3 /path/to/daily_collect.py

# ── WEEKLY ──────────────────────────────────────────────
  0 9    * * 6     /usr/bin/python3 /path/to/weekly_collect.py

# ── MONTHLY ─────────────────────────────────────────────
  0 9    1 * *     /usr/bin/python3 /path/to/monthly_collect.py
```

| Schedule | Cron Expression | When | What |
|----------|-----------------|------|------|
| **Hourly** | `0 9-15 * * 1-5` | Every hour 9–15, Mon–Fri | Hourly OHLCV candles |
| **Daily** | `0 16 * * 1-5` | 4 PM, Mon–Fri | EOD OHLCV + Financials |
| **Weekly** | `0 9 * * 6` | 9 AM, Saturday | Weekly candles + News + Events |
| **Monthly** | `0 9 1 * *` | 9 AM, 1st of month | Monthly candles + Ownership + Reports |
