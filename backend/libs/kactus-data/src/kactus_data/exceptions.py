"""kactus-data internal exceptions."""

from __future__ import annotations

import pandas as pd


class RateLimitedError(Exception):
    """vnstock rate limit hit mid-crawl.

    vnai's quota guard raises ``SystemExit`` (a ``BaseException``) when the
    per-minute budget is exhausted; the fetch layer converts it into this
    ordinary exception so it can never escape past ``except Exception`` and
    kill the event loop.

    Carries the partial result: on the fetch side ``df`` holds the rows
    collected before the limit hit; the provider stores them, then re-raises
    with ``rows_stored`` set (and ``df`` dropped) so the job layer can finish
    FAILED with a full reason while keeping the data.
    """

    def __init__(
        self,
        *,
        done: int,
        total: int,
        rows_stored: int = 0,
        df: pd.DataFrame | None = None,
    ) -> None:
        self.done = done
        self.total = total
        self.rows_stored = rows_stored
        self.df = df
        super().__init__(f"vnstock rate limit after {done}/{total} codes")
