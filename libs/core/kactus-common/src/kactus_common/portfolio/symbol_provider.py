"""The IoC seam between kactus-fin and kactus-data.

``kactus-data`` crawl jobs are portfolio-ignorant: they accept a plain
``list[str]`` of codes.  ``kactus-fin`` knows the union of all users' watchlists
(plus a VN30/VN100 baseline) and injects it by implementing this Protocol.

Keeping the contract here (in kactus-common) means kactus-data never imports
kactus-fin, preserving the one-way dependency flow.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SymbolProvider(Protocol):
    """Supplies the codes to crawl, grouped by asset type.

    Keys are :class:`~kactus_common.portfolio.const.AssetType` *values*
    (strings, since ``AssetType`` is a ``StrEnum``); values are de-duplicated
    code lists.
    """

    async def get_codes_by_type(self) -> dict[str, list[str]]:
        """Return ``{asset_type: [code, ...]}`` for the next crawl."""
        ...
