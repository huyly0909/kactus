"""Gold price data sources — Vietnamese domestic and global.

Providers:
- VNAppMob: Vietnamese gold (SJC, DOJI, PNJ)
- Metals-API: Global precious metals (XAU, XAG, XPT, XPD)
- Mihong: Vietnamese gold (legacy)
"""

from kactus_data.sources.gold.metals_api import MetalsAPISource
from kactus_data.sources.gold.mihong import MihongGoldSource
from kactus_data.sources.gold.tables import GOLD_GLOBAL_TABLE, GOLD_VN_TABLE
from kactus_data.sources.gold.vnappmob import VNAppMobGoldSource

__all__ = [
    "MihongGoldSource",
    "VNAppMobGoldSource",
    "MetalsAPISource",
    "GOLD_VN_TABLE",
    "GOLD_GLOBAL_TABLE",
]
