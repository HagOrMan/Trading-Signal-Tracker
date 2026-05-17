"""Observation detectors. One function per type. Returns Observation | None.

Every detector takes a price DataFrame (with `adj_close` column, date-indexed)
and returns either an Observation (currently active) or None.

The `find_historical_*` helpers used by the honesty layer return the full set
of dates this observation would have fired throughout the history, not just
"currently active." Those live alongside the detector for proximity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import pandas as pd

from src import indicators
from src.observation_templates import render_template

OBSERVATION_TYPES = [
    "ma_crossover_bullish",
    "ma_crossover_bearish",
    "new_52w_high",
    "new_52w_low",
    "vol_regime_elevated",
    "vol_regime_compressed",
    "drawdown_significant",
    "correlation_decoupling",
]


@dataclass(frozen=True)
class Observation:
    ticker: str
    type: str
    headline: str
    what_happened: str
    what_camps_read_into_it: str
    what_to_consider: str
    detected_at: date
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _adj_close(prices: pd.DataFrame) -> pd.Series:
    """Return the adj_close column as a series; raises if missing."""
    if "adj_close" not in prices.columns:
        raise ValueError("prices DataFrame must contain an 'adj_close' column")
    return prices["adj_close"].dropna()


def _frame_from_template(
    ticker: str,
    obs_type: str,
    what_happened: str,
    detected_at: date,
    metadata: dict | None = None,
) -> Observation:
    """Build an Observation by pulling framing text from the template module."""
    rendered = render_template(obs_type, ticker)
    if rendered is None:
        raise KeyError(f"no template defined for observation type {obs_type!r}")
    return Observation(
        ticker=ticker,
        type=obs_type,
        headline=rendered["headline"],
        what_happened=what_happened,
        what_camps_read_into_it=rendered["what_camps_read_into_it"],
        what_to_consider=rendered["what_to_consider"],
        detected_at=detected_at,
        metadata=metadata or {},
    )


def _index_to_date(idx) -> date:
    """Normalize a pandas DatetimeIndex value to a stdlib date."""
    if isinstance(idx, (datetime, pd.Timestamp)):
        return idx.date() if hasattr(idx, "date") else idx
    return idx


# ---------------------------------------------------------------------------
# MA crossovers
# ---------------------------------------------------------------------------


def _crossover_above_dates(short: pd.Series, long: pd.Series) -> list[pd.Timestamp]:
    """Dates where `short` crossed strictly from <= long to > long."""
    aligned = pd.concat([short, long], axis=1, join="inner").dropna()
    if aligned.empty:
        return []
    s, l = aligned.iloc[:, 0], aligned.iloc[:, 1]
    crossings = (s > l) & (s.shift(1) <= l.shift(1))
    return list(aligned.index[crossings.fillna(False)])


def _crossover_below_dates(short: pd.Series, long: pd.Series) -> list[pd.Timestamp]:
    aligned = pd.concat([short, long], axis=1, join="inner").dropna()
    if aligned.empty:
        return []
    s, l = aligned.iloc[:, 0], aligned.iloc[:, 1]
    crossings = (s < l) & (s.shift(1) >= l.shift(1))
    return list(aligned.index[crossings.fillna(False)])


def detect_ma_crossover_bullish(
    ticker: str,
    prices: pd.DataFrame,
    short_window: int = 50,
    long_window: int = 200,
    lookback_days: int = 30,
) -> Observation | None:
    """Fire if 50d MA crossed above 200d MA in the last `lookback_days`."""
    close = _adj_close(prices)
    if len(close) < long_window + 1:
        return None
    short = indicators.moving_average(close, short_window)
    long = indicators.moving_average(close, long_window)
    crosses = _crossover_above_dates(short, long)
    if not crosses:
        return None
    most_recent = crosses[-1]
    days_since = (close.index[-1] - most_recent).days
    if days_since > lookback_days:
        return None
    what_happened = (
        f"The {short_window}-day moving average crossed above the {long_window}-day "
        f"on {most_recent.date().isoformat()} ({days_since} trading days ago). "
        f"Current price: {close.iloc[-1]:.2f}."
    )
    return _frame_from_template(
        ticker,
        "ma_crossover_bullish",
        what_happened,
        detected_at=_index_to_date(close.index[-1]),
        metadata={
            "cross_date": most_recent.date().isoformat(),
            "days_since": days_since,
        },
    )


def detect_ma_crossover_bearish(
    ticker: str,
    prices: pd.DataFrame,
    short_window: int = 50,
    long_window: int = 200,
    lookback_days: int = 30,
) -> Observation | None:
    """Fire if 50d MA crossed below 200d MA in the last `lookback_days`."""
    close = _adj_close(prices)
    if len(close) < long_window + 1:
        return None
    short = indicators.moving_average(close, short_window)
    long = indicators.moving_average(close, long_window)
    crosses = _crossover_below_dates(short, long)
    if not crosses:
        return None
    most_recent = crosses[-1]
    days_since = (close.index[-1] - most_recent).days
    if days_since > lookback_days:
        return None
    what_happened = (
        f"The {short_window}-day moving average crossed below the {long_window}-day "
        f"on {most_recent.date().isoformat()} ({days_since} trading days ago). "
        f"Current price: {close.iloc[-1]:.2f}."
    )
    return _frame_from_template(
        ticker,
        "ma_crossover_bearish",
        what_happened,
        detected_at=_index_to_date(close.index[-1]),
        metadata={
            "cross_date": most_recent.date().isoformat(),
            "days_since": days_since,
        },
    )


def find_historical_crossovers(
    prices: pd.DataFrame,
    direction: str,
    short_window: int = 50,
    long_window: int = 200,
) -> list[pd.Timestamp]:
    """Return all historical crossover dates. `direction` is 'bullish' or 'bearish'."""
    close = _adj_close(prices)
    if len(close) < long_window + 1:
        return []
    short = indicators.moving_average(close, short_window)
    long = indicators.moving_average(close, long_window)
    if direction == "bullish":
        return _crossover_above_dates(short, long)
    if direction == "bearish":
        return _crossover_below_dates(short, long)
    raise ValueError(f"direction must be 'bullish' or 'bearish', got {direction!r}")


# ---------------------------------------------------------------------------
# 52-week high / low
# ---------------------------------------------------------------------------

_52W = 252


def _new_high_dates(close: pd.Series) -> list[pd.Timestamp]:
    """Dates where close > max of the prior 252 trading days (exclusive)."""
    prior_max = close.shift(1).rolling(window=_52W, min_periods=_52W).max()
    flags = (close > prior_max).fillna(False)
    return list(close.index[flags])


def _new_low_dates(close: pd.Series) -> list[pd.Timestamp]:
    prior_min = close.shift(1).rolling(window=_52W, min_periods=_52W).min()
    flags = (close < prior_min).fillna(False)
    return list(close.index[flags])


def detect_new_52w_high(
    ticker: str, prices: pd.DataFrame, lookback_days: int = 5
) -> Observation | None:
    """Fire if {ticker} closed above prior 52w high in the last `lookback_days`."""
    close = _adj_close(prices)
    if len(close) < _52W + 1:
        return None
    highs = _new_high_dates(close)
    if not highs:
        return None
    last_high = highs[-1]
    days_since = (close.index[-1] - last_high).days
    if days_since > lookback_days:
        return None
    what_happened = (
        f"{ticker} closed at {close.loc[last_high]:.2f} on "
        f"{last_high.date().isoformat()}, above its prior 52-week high "
        f"({days_since} trading days ago)."
    )
    return _frame_from_template(
        ticker,
        "new_52w_high",
        what_happened,
        detected_at=_index_to_date(close.index[-1]),
        metadata={"high_date": last_high.date().isoformat(), "days_since": days_since},
    )


def detect_new_52w_low(
    ticker: str, prices: pd.DataFrame, lookback_days: int = 5
) -> Observation | None:
    """Fire if {ticker} closed below prior 52w low in the last `lookback_days`."""
    close = _adj_close(prices)
    if len(close) < _52W + 1:
        return None
    lows = _new_low_dates(close)
    if not lows:
        return None
    last_low = lows[-1]
    days_since = (close.index[-1] - last_low).days
    if days_since > lookback_days:
        return None
    what_happened = (
        f"{ticker} closed at {close.loc[last_low]:.2f} on "
        f"{last_low.date().isoformat()}, below its prior 52-week low "
        f"({days_since} trading days ago)."
    )
    return _frame_from_template(
        ticker,
        "new_52w_low",
        what_happened,
        detected_at=_index_to_date(close.index[-1]),
        metadata={"low_date": last_low.date().isoformat(), "days_since": days_since},
    )


def find_historical_new_highs(prices: pd.DataFrame) -> list[pd.Timestamp]:
    close = _adj_close(prices)
    if len(close) < _52W + 1:
        return []
    return _new_high_dates(close)


def find_historical_new_lows(prices: pd.DataFrame) -> list[pd.Timestamp]:
    close = _adj_close(prices)
    if len(close) < _52W + 1:
        return []
    return _new_low_dates(close)


# ---------------------------------------------------------------------------
# Volatility regime
# ---------------------------------------------------------------------------


def _vol_regime_dates(
    close: pd.Series,
    direction: str,
    vol_window_days: int = 30,
    lookback_years: int = 2,
    top_pct: float = 0.10,
) -> list[pd.Timestamp]:
    """Dates where 30d vol entered the top or bottom decile of a 2y window.

    Returns dates of first-day-of-regime crossings, not every day in the regime —
    so the honesty layer measures forward returns from regime *onset*.
    """
    vol = indicators.rolling_volatility(close, vol_window_days).dropna()
    lookback = lookback_years * 252
    if len(vol) < lookback + 1:
        return []
    # For each date t, compute the percentile rank of vol[t] within vol[t-lookback:t].
    rolling_pct = vol.rolling(window=lookback, min_periods=lookback).apply(
        lambda window: (window <= window.iloc[-1]).mean(), raw=False
    )
    if direction == "elevated":
        in_regime = rolling_pct >= (1 - top_pct)
    elif direction == "compressed":
        in_regime = rolling_pct <= top_pct
    else:
        raise ValueError("direction must be 'elevated' or 'compressed'")
    in_regime = in_regime.fillna(False)
    onsets = in_regime & ~in_regime.shift(1, fill_value=False)
    return list(in_regime.index[onsets])


def detect_vol_regime_elevated(
    ticker: str,
    prices: pd.DataFrame,
    vol_window_days: int = 30,
    lookback_years: int = 2,
    top_pct: float = 0.10,
) -> Observation | None:
    """Fire if current 30d vol is in the top 10% of the 2-year history."""
    close = _adj_close(prices)
    vol = indicators.rolling_volatility(close, vol_window_days).dropna()
    lookback = lookback_years * 252
    if len(vol) < lookback + 1:
        return None
    window = vol.tail(lookback)
    current = vol.iloc[-1]
    pct = float((window <= current).mean())
    if pct < (1 - top_pct):
        return None
    what_happened = (
        f"30-day realized volatility on {ticker} is {current * 100:.1f}% "
        f"(annualized), at the {pct * 100:.0f}th percentile of the trailing "
        f"{lookback_years}-year range."
    )
    return _frame_from_template(
        ticker,
        "vol_regime_elevated",
        what_happened,
        detected_at=_index_to_date(close.index[-1]),
        metadata={"current_vol": float(current), "percentile": pct},
    )


def detect_vol_regime_compressed(
    ticker: str,
    prices: pd.DataFrame,
    vol_window_days: int = 30,
    lookback_years: int = 2,
    top_pct: float = 0.10,
) -> Observation | None:
    """Fire if current 30d vol is in the bottom 10% of the 2-year history."""
    close = _adj_close(prices)
    vol = indicators.rolling_volatility(close, vol_window_days).dropna()
    lookback = lookback_years * 252
    if len(vol) < lookback + 1:
        return None
    window = vol.tail(lookback)
    current = vol.iloc[-1]
    pct = float((window <= current).mean())
    if pct > top_pct:
        return None
    what_happened = (
        f"30-day realized volatility on {ticker} is {current * 100:.1f}% "
        f"(annualized), at the {pct * 100:.0f}th percentile of the trailing "
        f"{lookback_years}-year range."
    )
    return _frame_from_template(
        ticker,
        "vol_regime_compressed",
        what_happened,
        detected_at=_index_to_date(close.index[-1]),
        metadata={"current_vol": float(current), "percentile": pct},
    )


def find_historical_vol_regime(
    prices: pd.DataFrame,
    direction: str,
    vol_window_days: int = 30,
    lookback_years: int = 2,
    top_pct: float = 0.10,
) -> list[pd.Timestamp]:
    close = _adj_close(prices)
    return _vol_regime_dates(
        close,
        direction,
        vol_window_days=vol_window_days,
        lookback_years=lookback_years,
        top_pct=top_pct,
    )


# ---------------------------------------------------------------------------
# Significant drawdown
# ---------------------------------------------------------------------------


def detect_drawdown_significant(
    ticker: str,
    prices: pd.DataFrame,
    drawdown_pct: float = 15.0,
    lookback_days: int = 252,
) -> Observation | None:
    """Fire if current price is more than `drawdown_pct`% below the trailing 1y high."""
    close = _adj_close(prices)
    if len(close) < lookback_days:
        return None
    dd = indicators.drawdown_from_high(close, lookback_days)
    current = dd.iloc[-1]
    if pd.isna(current) or current > -drawdown_pct / 100.0:
        return None
    high_window = close.tail(lookback_days)
    peak_value = float(high_window.max())
    peak_date = high_window.idxmax().date().isoformat()
    what_happened = (
        f"{ticker} is currently {abs(current) * 100:.1f}% below its trailing "
        f"{lookback_days}-day high of {peak_value:.2f} (reached {peak_date})."
    )
    return _frame_from_template(
        ticker,
        "drawdown_significant",
        what_happened,
        detected_at=_index_to_date(close.index[-1]),
        metadata={
            "drawdown_pct": float(abs(current) * 100),
            "peak_value": peak_value,
            "peak_date": peak_date,
        },
    )


def find_historical_drawdowns(
    prices: pd.DataFrame,
    drawdown_pct: float = 15.0,
    lookback_days: int = 252,
) -> list[pd.Timestamp]:
    """Dates where drawdown first crossed below the threshold (regime onset)."""
    close = _adj_close(prices)
    if len(close) < lookback_days + 1:
        return []
    dd = indicators.drawdown_from_high(close, lookback_days)
    threshold = -drawdown_pct / 100.0
    below = (dd <= threshold).fillna(False)
    onsets = below & ~below.shift(1, fill_value=False)
    return list(dd.index[onsets])


# ---------------------------------------------------------------------------
# Correlation decoupling
# ---------------------------------------------------------------------------


def detect_correlation_decoupling(
    ticker: str,
    prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame | None,
    window_days: int = 60,
    drop_threshold: float = 0.3,
) -> Observation | None:
    """Fire if 60d correlation dropped >`drop_threshold` from 1y average."""
    if benchmark_prices is None or benchmark_prices.empty:
        return None
    close = _adj_close(prices)
    bench = _adj_close(benchmark_prices)
    aligned = pd.concat(
        [close.rename("a"), bench.rename("b")], axis=1, join="inner"
    ).dropna()
    if len(aligned) < 252 + window_days:
        return None
    a_ret = indicators.log_returns(aligned["a"])
    b_ret = indicators.log_returns(aligned["b"])
    rolling = indicators.rolling_correlation(a_ret, b_ret, window_days).dropna()
    if len(rolling) < 252:
        return None
    current = float(rolling.iloc[-1])
    avg_1y = float(rolling.tail(252).mean())
    drop = avg_1y - current
    if drop < drop_threshold:
        return None
    what_happened = (
        f"{window_days}-day correlation between {ticker} and the benchmark is "
        f"{current:.2f}, vs. a 1-year average of {avg_1y:.2f} (a drop of "
        f"{drop:.2f})."
    )
    return _frame_from_template(
        ticker,
        "correlation_decoupling",
        what_happened,
        detected_at=_index_to_date(aligned.index[-1]),
        metadata={
            "current_corr": current,
            "avg_1y_corr": avg_1y,
            "drop": drop,
        },
    )


def find_historical_decouplings(
    prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame | None,
    window_days: int = 60,
    drop_threshold: float = 0.3,
) -> list[pd.Timestamp]:
    if benchmark_prices is None or benchmark_prices.empty:
        return []
    close = _adj_close(prices)
    bench = _adj_close(benchmark_prices)
    aligned = pd.concat(
        [close.rename("a"), bench.rename("b")], axis=1, join="inner"
    ).dropna()
    if len(aligned) < 252 + window_days:
        return []
    a_ret = indicators.log_returns(aligned["a"])
    b_ret = indicators.log_returns(aligned["b"])
    rolling = indicators.rolling_correlation(a_ret, b_ret, window_days).dropna()
    if len(rolling) < 252:
        return []
    avg_1y_series = rolling.rolling(window=252, min_periods=252).mean()
    drop = (avg_1y_series - rolling).fillna(0)
    flag = drop >= drop_threshold
    onsets = flag & ~flag.shift(1, fill_value=False)
    return list(rolling.index[onsets])


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_BASIC_DETECTORS: list[Callable[..., Observation | None]] = [
    detect_ma_crossover_bullish,
    detect_ma_crossover_bearish,
    detect_new_52w_high,
    detect_new_52w_low,
    detect_vol_regime_elevated,
    detect_vol_regime_compressed,
    detect_drawdown_significant,
]


def get_active_observations(
    ticker: str,
    prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame | None = None,
) -> list[Observation]:
    """Run every detector. Return all currently-active observations.

    `benchmark_prices` is only used for `correlation_decoupling` — pass `None`
    when no benchmark data is available and that detector will be skipped.
    """
    out: list[Observation] = []
    if prices is None or prices.empty:
        return out
    for fn in _BASIC_DETECTORS:
        try:
            obs = fn(ticker, prices)
        except Exception:  # noqa: BLE001 — detectors must never crash the UI
            continue
        if obs is not None:
            out.append(obs)
    try:
        decoupling = detect_correlation_decoupling(ticker, prices, benchmark_prices)
        if decoupling is not None:
            out.append(decoupling)
    except Exception:  # noqa: BLE001
        pass
    return out


def find_historical_instances(
    prices: pd.DataFrame,
    observation_type: str,
    benchmark_prices: pd.DataFrame | None = None,
) -> list[date]:
    """Return all historical dates where `observation_type` fired on `prices`."""
    if observation_type == "ma_crossover_bullish":
        ts = find_historical_crossovers(prices, "bullish")
    elif observation_type == "ma_crossover_bearish":
        ts = find_historical_crossovers(prices, "bearish")
    elif observation_type == "new_52w_high":
        ts = find_historical_new_highs(prices)
    elif observation_type == "new_52w_low":
        ts = find_historical_new_lows(prices)
    elif observation_type == "vol_regime_elevated":
        ts = find_historical_vol_regime(prices, "elevated")
    elif observation_type == "vol_regime_compressed":
        ts = find_historical_vol_regime(prices, "compressed")
    elif observation_type == "drawdown_significant":
        ts = find_historical_drawdowns(prices)
    elif observation_type == "correlation_decoupling":
        ts = find_historical_decouplings(prices, benchmark_prices)
    else:
        raise ValueError(f"unknown observation type: {observation_type!r}")
    return [t.date() if hasattr(t, "date") else t for t in ts]
