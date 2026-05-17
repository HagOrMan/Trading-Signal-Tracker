"""Tests for src.indicators with synthetic price series."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src import indicators


def _const_series(value: float, n: int) -> pd.Series:
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series([value] * n, index=idx)


def _linear_series(start: float, step: float, n: int) -> pd.Series:
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.Series([start + step * i for i in range(n)], index=idx)


def test_moving_average_constant_series() -> None:
    s = _const_series(100.0, 50)
    ma = indicators.moving_average(s, 10)
    # First 9 values are NaN; rest are 100.
    assert ma.iloc[:9].isna().all()
    assert ma.iloc[9:].eq(100.0).all()


def test_moving_average_invalid_window() -> None:
    with pytest.raises(ValueError):
        indicators.moving_average(_const_series(1, 10), 0)


def test_rolling_volatility_constant_is_zero() -> None:
    s = _const_series(100.0, 60)
    vol = indicators.rolling_volatility(s, 30).dropna()
    assert vol.iloc[-1] == pytest.approx(0.0)


def test_rolling_max_min() -> None:
    s = _linear_series(100.0, 1.0, 20)  # 100, 101, ..., 119
    mx = indicators.rolling_max(s, 5)
    mn = indicators.rolling_min(s, 5)
    # Last 5-window max is 119; min is 115.
    assert mx.iloc[-1] == 119.0
    assert mn.iloc[-1] == 115.0


def test_drawdown_from_high() -> None:
    # Build a series: 100, 110, 120, 100, 90 — 1y window covers all
    idx = pd.date_range("2020-01-01", periods=5, freq="B")
    s = pd.Series([100, 110, 120, 100, 90], index=idx, dtype=float)
    dd = indicators.drawdown_from_high(s, 5)
    # Final price 90, high in window 120 → drawdown = -0.25
    assert dd.iloc[-1] == pytest.approx(-0.25)


def test_rolling_correlation_perfect_positive() -> None:
    s = _linear_series(100, 1.0, 100)
    # Perfectly correlated copy (with slight different scale)
    c = s * 2.5 + 10
    a_ret = indicators.log_returns(s)
    b_ret = indicators.log_returns(c)
    corr = indicators.rolling_correlation(a_ret, b_ret, 30).dropna()
    assert corr.iloc[-1] == pytest.approx(1.0)


def test_percentile_rank_basic() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert indicators.percentile_rank(s, 3.0) == pytest.approx(0.6)
    assert indicators.percentile_rank(s, 5.0) == pytest.approx(1.0)
    assert indicators.percentile_rank(s, 0.0) == pytest.approx(0.0)


def test_percentile_rank_empty_series() -> None:
    assert indicators.percentile_rank(pd.Series([], dtype=float), 1.0) is None


def test_forward_return_basic() -> None:
    s = pd.Series([100, 105, 110, 121, 100])
    # forward 2 days from idx 1 (105) → idx 3 (121): 121/105 - 1
    assert indicators.forward_return(s, 1, 2) == pytest.approx(121 / 105 - 1)


def test_forward_return_out_of_bounds() -> None:
    s = pd.Series([100, 101, 102])
    assert indicators.forward_return(s, 1, 10) is None
