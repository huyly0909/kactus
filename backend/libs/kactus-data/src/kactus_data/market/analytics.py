"""Derived scores — the two read models vnstock does not serve.

vnstock has no indicator or scoring surface, so the technical consensus gauge
and the 5-axis fundamental radar are computed here from data already in DuckDB:

    technical_gauge()   ← stock_ohlcv    (indicator vote, TradingView-style)
    fundamental_radar() ← stock_ratios   (percentile rank vs comparable peers)

Pure pandas/numpy on purpose. ``ta``/``pandas-ta`` would add a heavy,
version-fragile dependency for ~120 lines of arithmetic, and pinning the maths
in our own code is what makes the numbers reproducible and testable.

These are *our* scores. The axes and the 0-10 presentation match what public
sites show, but the metric weights are our choice — agreement with any
particular site is not the bar, and the API labels them as derived.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Technical
# --------------------------------------------------------------------------- #
MA_PERIODS = (10, 20, 50, 100, 200)
MIN_BARS = 20  # below this no indicator has warmed up enough to vote

BUY, NEUTRAL, SELL = 1, 0, -1
_LABELS = {BUY: "BUY", NEUTRAL: "NEUTRAL", SELL: "SELL"}

# Consensus bands over the mean vote in [-1, 1], best first. The neutral band is
# open at its lower edge so that exactly -0.1 reads SELL rather than NEUTRAL,
# mirroring the closed upper edge at +0.1.
_BANDS: tuple[tuple[float, bool, str], ...] = (
    (0.5, True, "STRONG_BUY"),
    (0.1, True, "BUY"),
    (-0.1, False, "NEUTRAL"),
    (-0.5, False, "SELL"),
)
_WORST = "STRONG_SELL"


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rma(s: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothing — RSI and ADX use this, not a plain EMA."""
    return s.ewm(alpha=1 / n, adjust=False).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = _rma(delta.clip(lower=0), n)
    loss = _rma((-delta).clip(lower=0), n)
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _stoch(df: pd.DataFrame, n: int = 14, d: int = 3) -> tuple[pd.Series, pd.Series]:
    low_n = df["low"].rolling(n).min()
    high_n = df["high"].rolling(n).max()
    span = (high_n - low_n).replace(0, np.nan)
    k = ((df["close"] - low_n) / span * 100).rolling(d).mean()
    return k, k.rolling(d).mean()


def _cci(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(n).mean()
    # Mean absolute deviation, not standard deviation — the 0.015 constant is
    # calibrated to MAD.
    mad = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma) / (0.015 * mad.replace(0, np.nan))


def _adx(df: pd.DataFrame, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = _rma(tr, n).replace(0, np.nan)
    plus_di = 100 * _rma(pd.Series(plus_dm, index=df.index), n) / atr
    minus_di = 100 * _rma(pd.Series(minus_dm, index=df.index), n) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _rma(dx, n), plus_di, minus_di


def _williams_r(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high_n = df["high"].rolling(n).max()
    low_n = df["low"].rolling(n).min()
    span = (high_n - low_n).replace(0, np.nan)
    return -100 * (high_n - df["close"]) / span


def _last(s: pd.Series) -> float | None:
    """Last finite value, or None — indicators warm up with NaN."""
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return float(s.iloc[-1]) if len(s) else None


def resample_ohlcv(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Roll daily candles up to weekly/monthly. ``df`` is indexed by bar time."""
    rule = {"1D": None, "1W": "W", "1M": "ME"}.get(interval)
    if rule is None:
        return df
    out = df.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return out.dropna(subset=["close"])


def _label_for(score: float) -> str:
    for threshold, inclusive, label in _BANDS:
        if (score >= threshold) if inclusive else (score > threshold):
            return label
    return _WORST


def technical_gauge(df: pd.DataFrame, interval: str = "1D") -> dict:
    """Indicator vote over candles → consensus label + per-signal breakdown.

    ``df`` needs a datetime index and open/high/low/close/volume columns,
    oldest first. Signals that have not warmed up are *dropped* rather than
    counted neutral: a 200-day average over 60 bars is not a neutral reading,
    it is no reading, and counting it would drag every score toward the middle.
    """
    df = resample_ohlcv(df, interval)
    if len(df) < MIN_BARS:
        return {
            "interval": interval,
            "bars": int(len(df)),
            "price": None,
            "label": "NO_DATA",
            "score": None,
            "counts": {"buy": 0, "neutral": 0, "sell": 0},
            "signals": [],
        }

    close = df["close"]
    price = float(close.iloc[-1])
    signals: list[dict] = []

    def add(name: str, group: str, value: float | None, vote: int | None) -> None:
        if value is None or vote is None:
            return
        signals.append(
            {
                "name": name,
                "group": group,
                "value": round(value, 4),
                "vote": _LABELS[vote],
                "_v": vote,
            }
        )

    # -- oscillators -------------------------------------------------------- #
    rsi = _last(_rsi(close))
    add(
        "RSI(14)",
        "oscillator",
        rsi,
        None if rsi is None else BUY if rsi < 30 else SELL if rsi > 70 else NEUTRAL,
    )

    k_s, d_s = _stoch(df)
    k, d = _last(k_s), _last(d_s)
    if k is not None and d is not None:
        # Oversold only counts as a buy while %K is turning up through %D —
        # otherwise a stock in freefall reads as a buy the whole way down.
        add(
            "Stoch %K(14,3,3)",
            "oscillator",
            k,
            BUY if (k < 20 and k > d) else SELL if (k > 80 and k < d) else NEUTRAL,
        )

    cci = _last(_cci(df))
    add(
        "CCI(20)",
        "oscillator",
        cci,
        None if cci is None else BUY if cci < -100 else SELL if cci > 100 else NEUTRAL,
    )

    adx_s, pdi_s, mdi_s = _adx(df)
    adx, pdi, mdi = _last(adx_s), _last(pdi_s), _last(mdi_s)
    if adx is not None and pdi is not None and mdi is not None:
        # ADX measures trend *strength* only; direction comes from the DI
        # crossover, and below 20 there is no trend to take a side on.
        add(
            "ADX(14)",
            "oscillator",
            adx,
            NEUTRAL if adx < 20 else BUY if pdi > mdi else SELL,
        )

    macd_line = _ema(close, 12) - _ema(close, 26)
    signal_line = _ema(macd_line, 9)
    macd, sig = _last(macd_line), _last(signal_line)
    if macd is not None and sig is not None:
        add("MACD(12,26,9)", "oscillator", macd, BUY if macd > sig else SELL)

    wr = _last(_williams_r(df))
    add(
        "Williams %R(14)",
        "oscillator",
        wr,
        None if wr is None else BUY if wr < -80 else SELL if wr > -20 else NEUTRAL,
    )

    mom = _last(close.diff(10))
    add(
        "Momentum(10)",
        "oscillator",
        mom,
        None if mom is None else BUY if mom > 0 else SELL if mom < 0 else NEUTRAL,
    )

    # -- moving averages ---------------------------------------------------- #
    for n in MA_PERIODS:
        if len(close) < n:
            continue
        for kind, series in (("SMA", close.rolling(n).mean()), ("EMA", _ema(close, n))):
            ma = _last(series)
            add(
                f"{kind}({n})",
                "moving_average",
                ma,
                None if ma is None else BUY if price > ma else SELL,
            )

    votes = [s.pop("_v") for s in signals]
    counts = {
        "buy": sum(1 for v in votes if v == BUY),
        "neutral": sum(1 for v in votes if v == NEUTRAL),
        "sell": sum(1 for v in votes if v == SELL),
    }
    score = float(np.mean(votes)) if votes else 0.0
    return {
        "interval": interval,
        "bars": int(len(df)),
        "price": price,
        "label": _label_for(score),
        "score": round(score, 4),
        "counts": counts,
        "signals": signals,
    }


# --------------------------------------------------------------------------- #
# Fundamental
# --------------------------------------------------------------------------- #
# (metric, higher_is_better) per axis.
#
# Banks get their own map. vnstock returns 0.0 (not null) for every banking
# field on a non-bank, and ``current_ratio`` / inventory days are meaningless
# for a bank — scoring both groups from one map would rank each against metrics
# that are structurally zero on the other side.
AXES_GENERAL: dict[str, list[tuple[str, bool]]] = {
    "Activity": [
        ("asset_turnover", True),
        ("fixed_asset_turnover", True),
        ("days_sales_outstanding", False),
        ("days_inventory_outstanding", False),
        ("cash_cycle", False),
    ],
    "Liquidity": [
        ("current_ratio", True),
        ("quick_ratio", True),
        ("cash_ratio", True),
    ],
    "Profitability": [
        ("roe", True),
        ("roa", True),
        ("roic", True),
        ("net_margin", True),
        ("gross_margin", True),
        ("ebit_margin", True),
    ],
    "Solvency": [
        ("debt_to_equity", False),
        ("financial_leverage", False),
        ("equity_to_assets", True),
        ("ev_to_ebitda", False),
    ],
    "Valuation": [
        ("pe_ratio", False),
        ("pb_ratio", False),
        ("ps_ratio", False),
        ("dividend_yield", True),
        ("price_to_cash_flow", False),
    ],
}

AXES_BANK: dict[str, list[tuple[str, bool]]] = {
    "Activity": [
        ("loans_growth", True),
        ("deposit_growth", True),
        ("asset_turnover", True),
    ],
    "Liquidity": [
        ("ldr", False),
        ("casa_ratio", True),
        ("equity_to_liabilities", True),
    ],
    "Profitability": [
        ("roe", True),
        ("roa", True),
        ("net_interest_margin", True),
        ("cost_to_income_ratio", False),
        ("non_interest_income", True),
    ],
    "Solvency": [
        ("npl", False),
        ("car", True),
        ("equity_to_assets", True),
        ("loan_loss_reserves_to_npls", True),
    ],
    "Valuation": [
        ("pe_ratio", False),
        ("pb_ratio", False),
        ("dividend_yield", True),
    ],
}

AXIS_ORDER = ("Activity", "Liquidity", "Profitability", "Solvency", "Valuation")
MIN_PEERS = 4  # below this a percentile rank is noise, not a ranking
INDUSTRY_BASELINE = 5.0  # a median peer is the 50th percentile by construction

_GRADES = ((8.0, "A"), (6.5, "B"), (5.0, "C"), (3.5, "D"))


def _grade(score: float) -> str:
    for threshold, letter in _GRADES:
        if score >= threshold:
            return letter
    return "F"


def fundamental_radar(
    peers: pd.DataFrame, symbol: str, *, is_bank: bool = False
) -> dict:
    """Percentile-rank one symbol's ratios against its peers, 5 axes × 0-10.

    ``peers`` is one row per symbol (index = symbol) of that symbol's latest
    ratio metrics, already restricted to comparable companies. Scoring is
    relative: a 10 on Profitability means best-in-peer-group, not good in
    absolute terms.
    """
    axes_map = AXES_BANK if is_bank else AXES_GENERAL
    symbol = symbol.upper()
    if peers.empty or symbol not in peers.index:
        return {"symbol": symbol, "available": False, "reason": "no ratio data"}
    if len(peers) < MIN_PEERS:
        return {
            "symbol": symbol,
            "available": False,
            "reason": f"only {len(peers)} peers with ratio data (need {MIN_PEERS})",
        }

    axes: list[dict] = []
    for axis in AXIS_ORDER:
        metrics: list[dict] = []
        for metric, higher_better in axes_map.get(axis, []):
            if metric not in peers.columns:
                continue
            col = pd.to_numeric(peers[metric], errors="coerce")
            col = col.replace([np.inf, -np.inf], np.nan)
            # vnstock fills inapplicable ratios with 0.0 rather than null, so an
            # all-zero column carries no ranking information at all.
            if col.notna().sum() < MIN_PEERS or bool((col.fillna(0) == 0).all()):
                continue
            # A negative P/E or P/B means loss-making, not cheap — drop those
            # rather than letting them top an inverted metric.
            if not higher_better:
                col = col.where(col > 0)
            pct = col.rank(pct=True, ascending=higher_better)
            value, rank = col.get(symbol), pct.get(symbol)
            if pd.isna(rank):
                continue
            metrics.append(
                {
                    "metric": metric,
                    "value": None if pd.isna(value) else round(float(value), 6),
                    "percentile": round(float(rank), 4),
                    "peer_median": round(float(col.median()), 6),
                }
            )
        score = (
            round(float(np.mean([m["percentile"] for m in metrics])) * 10, 2)
            if metrics
            else None
        )
        axes.append(
            {
                "axis": axis,
                "score": score,
                "industry": INDUSTRY_BASELINE if metrics else None,
                "metrics": metrics,
            }
        )

    scored = [a["score"] for a in axes if a["score"] is not None]
    overall = round(float(np.mean(scored)), 2) if scored else None
    return {
        "symbol": symbol,
        "available": overall is not None,
        "is_bank": is_bank,
        "peers": int(len(peers)),
        "overall": overall,
        "grade": _grade(overall) if overall is not None else None,
        "axes": axes,
    }


def beta(
    stock_close: pd.Series, index_close: pd.Series, *, min_points: int = 30
) -> float | None:
    """Covariance of daily returns against the index, over overlapping dates."""
    joined = pd.concat(
        [stock_close.rename("s"), index_close.rename("i")], axis=1, join="inner"
    ).dropna()
    rets = joined.pct_change().dropna()
    if len(rets) < min_points:
        return None
    var = rets["i"].var()
    if not var:
        return None
    return round(float(rets["s"].cov(rets["i"]) / var), 4)
