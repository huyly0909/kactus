"""Gold price schemas."""

from __future__ import annotations

from kactus_common.schemas import BaseSchema


class GoldVnItem(BaseSchema):
    """Vietnamese gold price entry (SJC, DOJI, PNJ)."""

    brand: str
    type: str
    buy_price: float | None = None
    sell_price: float | None = None
    source: str | None = None
    synced_at: str | None = None


class GoldGlobalItem(BaseSchema):
    """Global precious metal price entry."""

    metal: str
    currency: str
    price: float | None = None
    source: str | None = None
    synced_at: str | None = None


class SyncGoldVnRequest(BaseSchema):
    """Request body for Vietnamese gold sync."""

    brand: str = "sjc"  # sjc, doji, pnj


class SyncGoldGlobalRequest(BaseSchema):
    """Request body for global gold sync."""

    metal: str = "XAU"  # XAU, XAG, XPT, XPD
