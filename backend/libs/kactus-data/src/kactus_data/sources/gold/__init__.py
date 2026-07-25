"""Gold price data sources."""

from kactus_data.sources.gold.mihong import MihongGoldSource
from kactus_data.sources.gold.sjc import SjcGoldSource
from kactus_data.sources.gold.yahoo import YahooGoldSource

__all__ = ["MihongGoldSource", "SjcGoldSource", "YahooGoldSource"]
