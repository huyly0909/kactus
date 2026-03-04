# VNStock API Documentation

> Comprehensive API documentation for the [vnstock](https://github.com/thinh-vu/vnstock) Python library — Vietnam stock market data pipeline.

---

## Table of Contents

| Document | Description |
|----------|-------------|
| [Authentication & Authorization](./authentication.md) | API keys, rate limits, DNSE trading auth flow |
| [API Reference](./api-reference.md) | Full API specification for all classes & methods |
| [Sequence Diagrams](./sequence-diagrams.md) | Auth flows, data pipeline, and architecture diagrams |
| [Data Collection & Cron Jobs](./data-collection.md) | Hourly, daily, weekly, monthly scheduling strategies |
| [Backfill Strategies](./backfill-strategies.md) | Initial and incremental data backfill patterns |

---

## Quick Start

```bash
pip install -U vnstock
```

```python
from vnstock import Quote

quote = Quote(symbol='VCI', source='KBS')
df = quote.history(start='2024-01-01', end='2024-12-31', interval='1D')
print(df)
```

---

## Key Facts

| Feature | Details |
|---------|---------|
| **Language** | Python |
| **Install** | `pip install -U vnstock` |
| **GitHub** | [github.com/thinh-vu/vnstock](https://github.com/thinh-vu/vnstock) |
| **License** | Open-source (free tier + paid Insider tiers) |
| **Data Format** | Pandas DataFrame |

---

## Data Sources

| Feature | KBS (KB Securities) | VCI (Vietcap Securities) |
|---------|---------------------|--------------------------|
| **Recommended for** | Google Colab / Kaggle | Local machine / Non-Google cloud |
| **Stability** | ✅ Very stable | ✅ Stable |
| **Data richness** | Standard | More comprehensive |
| **Historical OHLCV** | ✅ | ✅ |
| **Intraday trades** | ✅ | ✅ |
| **Trading board columns** | 29 columns (flat) | 77 columns (MultiIndex) |
| **ICB Classification** | ❌ | ✅ |
| **Bond data** | ❌ | ✅ |
| **Listed symbols** | ~1,557 | ~1,736 |

Additional source: **MSN** for international data (Forex, Crypto, Global Indices) — daily interval only.

---

## Limitations

| Limitation | Detail |
|------------|--------|
| **No WebSocket** | All real-time data is via HTTP polling, not push |
| **Rate Limits** | 20–500 req/min depending on tier |
| **Single-symbol API** | Each API call fetches data for 1 symbol (except `price_board`) |
| **Stock Screener** | Temporarily unavailable (was using TCBS, being replaced) |
| **International data** | Daily interval only (no intraday for Forex/Crypto) |
| **Colab restrictions** | VCI source may not work on Google Colab (use KBS + proxy) |
