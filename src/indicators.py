"""Pure indicator functions used by detectors and the honesty layer.

DEC-013: implemented directly with pandas — no pandas-ta. Each function takes
and returns a `pd.Series` (or DataFrame) so it composes cleanly.

Trading-year convention: 252 trading days / 21 trading days per month.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = 21


def moving_average(prices: pd.Series, window: int) -> pd.Series:
    """Simple moving average over `window` periods. NaN for the first window-1 rows."""
    if window <= 0:
        raise ValueError("window must be positive")
    return prices.rolling(window=window, min_periods=window).mean()


def log_returns(prices: pd.Series) -> pd.Series:
    """Daily log returns. First row is NaN."""
    return np.log(prices / prices.shift(1))


def rolling_volatility(prices: pd.Series, window: int = 30) -> pd.Series:
    """Annualized rolling stdev of daily log returns over `window` days."""
    if window <= 1:
        raise ValueError("window must be > 1")
    rets = log_returns(prices)
    return rets.rolling(window=window, min_periods=window).std() * math.sqrt(
        TRADING_DAYS_PER_YEAR
    )


def rolling_max(prices: pd.Series, window: int) -> pd.Series:
    """Rolling maximum over `window` periods."""
    if window <= 0:
        raise ValueError("window must be positive")
    return prices.rolling(window=window, min_periods=window).max()


def rolling_min(prices: pd.Series, window: int) -> pd.Series:
    """Rolling minimum over `window` periods."""
    if window <= 0:
        raise ValueError("window must be positive")
    return prices.rolling(window=window, min_periods=window).min()


def drawdown_from_high(prices: pd.Series, window: int) -> pd.Series:
    """Current price as a signed fraction below the rolling-window high.

    Returns 0 when at the high; -0.20 means 20% below. Used by the
    `drawdown_significant` observation.
    """
    high = rolling_max(prices, window)
    return prices / high - 1.0


def rolling_correlation(
    a: pd.Series, b: pd.Series, window: int = 60
) -> pd.Series:
    """Rolling Pearson correlation of two aligned series."""
    if window <= 1:
        raise ValueError("window must be > 1")
    return a.rolling(window=window, min_periods=window).corr(b)


def percentile_rank(series: pd.Series, value: float, lookback: int | None = None) -> float | None:
    """Where `value` falls in the distribution of the last `lookback` rows. 0..1.

    `None` if the series has no usable values.
    """
    s = series.dropna()
    if lookback is not None:
        s = s.tail(lookback)
    if s.empty:
        return None
    return float((s <= value).mean())


def forward_return(prices: pd.Series, start_idx: int, horizon_days: int) -> float | None:
    """Forward return from `start_idx` to `start_idx + horizon_days`. None if OOB."""
    end_idx = start_idx + horizon_days
    if start_idx < 0 or end_idx >= len(prices):
        return None
    start = prices.iloc[start_idx]
    end = prices.iloc[end_idx]
    if pd.isna(start) or pd.isna(end) or start == 0:
        return None
    return float(end / start - 1.0)
