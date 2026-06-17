"""Portfolio domain constants and enums (asset-class agnostic)."""

from __future__ import annotations

from enum import StrEnum


class AssetType(StrEnum):
    """Asset classes a portfolio item can reference.

    ``COIN`` is reserved/deferred — no provider is registered yet, so it cannot
    be crawled, but the schema already accommodates it (no migration needed when
    a coin provider lands).
    """

    STOCK = "STOCK"
    GOLD = "GOLD"
    COIN = "COIN"


class CrawlKind(StrEnum):
    """The dataset a crawl run produces."""

    QUOTES = "quotes"
    NEWS = "news"
    FOREIGN_TRADE = "foreign_trade"
    RATIOS = "ratios"
    OHLCV = "ohlcv"
    EVENTS = "events"
    CATALOG = "catalog"  # supported-asset sync


class CrawlTrigger(StrEnum):
    """What initiated a crawl run."""

    CRON = "cron"
    MANUAL = "manual"


class CrawlStatus(StrEnum):
    """Lifecycle of a crawl run."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
