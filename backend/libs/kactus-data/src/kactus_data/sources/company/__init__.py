"""Company data sources — overview, shareholders, officers.

Providers:
- vnstock: VnstockCompanySource
"""

from kactus_data.sources.company.tables import COMPANY_TABLE
from kactus_data.sources.company.vnstock import VnstockCompanySource

__all__ = [
    "VnstockCompanySource",
    "COMPANY_TABLE",
]
