# Sequence Diagrams & Architecture

> Visual diagrams for authentication flows, data collection pipelines, and system architecture.

---

## 1. DNSE Trading Authentication Flow

Two-phase authentication: Level 1 (read-only JWT) and Level 2 (trading token via OTP).

```mermaid
sequenceDiagram
    participant User
    participant VnstockClient
    participant DNSE_API

    rect rgb(230, 245, 255)
        Note over User,DNSE_API: Phase 1 — Level 1 Authentication (Read Access)
        User->>VnstockClient: client = Trade()
        User->>VnstockClient: client.login(username, password)
        VnstockClient->>DNSE_API: POST /authenticate {username, password}
        DNSE_API-->>VnstockClient: 200 OK — JWT Token
        Note right of VnstockClient: JWT stored in session
    end

    rect rgba(228, 151, 35, 1)
        Note over User,DNSE_API: Phase 2 — Level 2 Authentication (Trading Access)
        User->>VnstockClient: client.email_otp()
        VnstockClient->>DNSE_API: POST /request-otp
        DNSE_API-->>User: OTP sent via Email (expires in 2 min)
        User->>VnstockClient: client.get_trading_token(otp='123456')
        VnstockClient->>DNSE_API: POST /verify-otp {otp, jwt_token}
        DNSE_API-->>VnstockClient: 200 OK — Trading Token (8hr validity)
        Note right of VnstockClient: Trading token enables order placement
    end
```

---

## 2. Daily Data Collection Flow

Scheduled at **16:00 VNT (Vietnam Time)** after market close (15:00 VNT). Runs Monday–Friday only.

```mermaid
sequenceDiagram
    participant Cron as Cron Scheduler
    participant Script as daily_collect.py
    participant Vnstock as VNStock Library
    participant Broker as Broker API (KBS/VCI)
    participant Storage as Storage (DB/Parquet)
    participant Alert as Alerting (Telegram)

    Cron->>Script: Trigger at 16:00 VNT (Mon-Fri)
    Script->>Vnstock: Listing.all_symbols()
    Vnstock->>Broker: GET /symbols
    Broker-->>Vnstock: Symbol list
    Vnstock-->>Script: DataFrame of symbols

    loop For each symbol (with rate limiting)
        Script->>Vnstock: Quote(symbol).history(interval='1D')
        Vnstock->>Broker: GET /ohlcv?symbol=X&interval=1D
        Broker-->>Vnstock: OHLCV data
        Vnstock-->>Script: DataFrame
        Script->>Storage: Upsert daily OHLCV
    end

    Script->>Vnstock: Finance(symbol).income_statement()
    Vnstock->>Broker: GET /financials
    Broker-->>Vnstock: Financial data
    Script->>Storage: Upsert financial reports

    Script->>Alert: Send summary notification
    Alert-->>Script: ✅ Delivered
```

---

## 3. Hourly Data Collection Flow

Runs every hour during market hours (**09:00–15:00 VNT**), Monday–Friday.

```mermaid
sequenceDiagram
    participant Cron as Cron Scheduler
    participant Script as hourly_collect.py
    participant Vnstock as VNStock Library
    participant Broker as Broker API (KBS/VCI)
    participant Storage as Storage (DB/Parquet)

    Cron->>Script: Trigger every hour (09:00-15:00 VNT, Mon-Fri)
    
    loop For each tracked symbol
        Script->>Vnstock: Quote(symbol).history(length='1D', interval='1H')
        Vnstock->>Broker: GET /ohlcv?symbol=X&interval=1H
        Broker-->>Vnstock: Hourly OHLCV data
        Vnstock-->>Script: DataFrame
        Script->>Storage: Upsert hourly candle
        Script->>Script: Sleep 1s (rate limit: 60 req/min)
    end

    Note over Script,Storage: ~7 hourly candles per stock per day
```

---

## 4. Near Real-Time Polling Flow

Continuous polling during market hours for live price updates, using `price_board()` (multi-symbol) or `intraday()` (single-symbol).

```mermaid
sequenceDiagram
    participant Poller as Poller Process
    participant Vnstock as VNStock Library
    participant Broker as Broker API
    participant Storage as Storage
    participant Alert as Alert System

    Note over Poller: Runs continuously 09:00-15:00 VNT

    loop Every 3–5 seconds
        Poller->>Vnstock: Trading.price_board(['VCI', 'VCB', 'ACB'])
        Vnstock->>Broker: GET /price_board?symbols=VCI,VCB,ACB
        Broker-->>Vnstock: Live price snapshot
        Vnstock-->>Poller: DataFrame (29 or 77 cols)
        Poller->>Storage: Store snapshot

        alt Price crosses threshold
            Poller->>Alert: Send price alert
        end
    end
```

---

## 5. Backfill Flow

One-time (or periodic) bulk historical data download with rate limiting.

```mermaid
sequenceDiagram
    participant Script as backfill.py
    participant Vnstock as VNStock Library
    participant Broker as Broker API
    participant Storage as Storage

    Script->>Vnstock: Listing.all_symbols()
    Vnstock->>Broker: GET /symbols
    Broker-->>Vnstock: ~1,500 symbols
    Vnstock-->>Script: Symbol list

    par Parallel Workers (max 3)
        loop For each symbol batch
            Script->>Vnstock: Quote(symbol).history(start, end, interval='1D')
            Vnstock->>Broker: GET /ohlcv?symbol=X
            Broker-->>Vnstock: Historical OHLCV
            Vnstock-->>Script: DataFrame
            Script->>Storage: Write to Parquet / DB
            Script->>Script: Sleep 1s per batch of 3 (rate limiting)
        end
    end

    Note over Script: ~25 min for ~1,500 stocks (Free tier, 60 req/min)
```

---

## 6. System Architecture — Data Pipeline Overview

```mermaid
graph TD
    subgraph Sources["Data Sources"]
        KBS["KBS<br/>(KB Securities)"]
        VCI["VCI<br/>(Vietcap Securities)"]
        MSN["MSN<br/>(International)"]
    end

    subgraph VnstockLib["VNStock Library"]
        Listing["Listing API"]
        Quote["Quote API"]
        Trading["Trading API"]
        Finance["Finance API"]
        Company["Company API"]
    end

    subgraph Collection["Collection Strategies"]
        Daily["🕐 Daily Job<br/>cron 16:00 Mon-Fri"]
        Hourly["🕐 Hourly Job<br/>cron 09-15 Mon-Fri"]
        RT["⚡ Near Real-Time<br/>poll every 3-5s"]
        Backfill["📦 Backfill<br/>one-time bulk load"]
    end

    subgraph Storage["Storage Layer"]
        Parquet["📁 Parquet Files"]
        DB["🗄️ Database<br/>(Postgres/MySQL)"]
        S3["☁️ Cloud Storage<br/>(S3/GCS)"]
    end

    subgraph Alerts["Alerting"]
        TG["📱 Telegram Bot"]
        Slack["💬 Slack Webhook"]
        Lark["🔔 Lark BotBuilder"]
    end

    KBS --> VnstockLib
    VCI --> VnstockLib
    MSN --> VnstockLib

    Listing --> Backfill
    Quote --> Daily
    Quote --> Hourly
    Quote --> RT
    Trading --> RT
    Finance --> Daily

    Daily --> Storage
    Hourly --> Storage
    RT --> Storage
    Backfill --> Storage

    Storage --> Alerts
```

---

## 7. Cron Job Schedule Overview

```mermaid
gantt
    title VNStock Data Collection Schedule (Vietnam Time, Mon-Fri)
    dateFormat HH:mm
    axisFormat %H:%M

    section Market Hours
    Market Open           :active,    09:00, 15:00

    section Hourly Collection
    Hour 09               :           09:00, 10:00
    Hour 10               :           10:00, 11:00
    Hour 11               :           11:00, 12:00
    Hour 12               :           12:00, 13:00
    Hour 13               :           13:00, 14:00
    Hour 14               :           14:00, 15:00

    section Real-Time Polling
    Continuous Polling     :active,    09:00, 15:00

    section Daily Collection
    Daily Job              :crit,      16:00, 17:00

    section Weekly/Monthly
    Weekly Report (Sat)    :           09:00, 10:00
    Monthly Report (1st)   :           09:00, 10:00
```
