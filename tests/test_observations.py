"""Tests for src.observations — synthetic series engineered to trigger detectors."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import observations


def _make_prices(values: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.DataFrame({"adj_close": values}, index=idx)


def _engineer_crossover_up(n_pre: int = 250, n_post: int = 10) -> pd.DataFrame:
    """Flat-then-rising series that produces a 50/200 golden cross.

    Long flat lull keeps both MAs at the same level; a sustained rise pulls the
    50d MA above the 200d MA somewhere in the post-period.
    """
    flat = [100.0] * n_pre
    rising = [100.0 + i * 3.0 for i in range(1, n_post + 1)]
    return _make_prices(flat + rising)


def _engineer_crossover_down(n_pre: int = 250, n_post: int = 10) -> pd.DataFrame:
    flat = [100.0] * n_pre
    falling = [100.0 - i * 3.0 for i in range(1, n_post + 1)]
    return _make_prices(flat + falling)


def test_detect_ma_crossover_bullish_triggers() -> None:
    # 250 flat days, then a short rise — cross fires on first rising day.
    # Keep the rise short so days_since stays under the 30-day lookback.
    flat = [100.0] * 250
    rising = [100.0 + i * 2.0 for i in range(1, 11)]  # 10 rising days
    prices = _make_prices(flat + rising)
    obs = observations.detect_ma_crossover_bullish("TEST", prices)
    assert obs is not None
    assert obs.type == "ma_crossover_bullish"
    assert "{ticker}" not in obs.headline  # template substitution happened
    assert "TEST" in obs.headline


def test_detect_ma_crossover_bullish_too_old_returns_none() -> None:
    # Cross happens at idx 250; we extend with a long flat tail past the lookback.
    flat = [100.0] * 250
    rising = [100.0 + i * 2.0 for i in range(1, 11)]
    tail = [120.0] * 100  # well past the 30-day window
    prices = _make_prices(flat + rising + tail)
    obs = observations.detect_ma_crossover_bullish("TEST", prices, lookback_days=30)
    assert obs is None


def test_detect_ma_crossover_bearish_triggers() -> None:
    flat = [100.0] * 250
    falling = [100.0 - i * 0.5 for i in range(1, 11)]  # 10 falling days
    prices = _make_prices(flat + falling)
    obs = observations.detect_ma_crossover_bearish("TEST", prices)
    assert obs is not None
    assert obs.type == "ma_crossover_bearish"


def test_detect_new_52w_high() -> None:
    # 252 days flat at 100, then a single new high
    flat = [100.0] * 260
    prices = _make_prices(flat + [101.0])
    obs = observations.detect_new_52w_high("TEST", prices, lookback_days=5)
    assert obs is not None
    assert obs.type == "new_52w_high"


def test_detect_new_52w_low() -> None:
    flat = [100.0] * 260
    prices = _make_prices(flat + [99.0])
    obs = observations.detect_new_52w_low("TEST", prices, lookback_days=5)
    assert obs is not None


def test_detect_new_52w_low_too_old() -> None:
    flat = [100.0] * 260
    prices = _make_prices(flat + [99.0] + [100.0] * 10)
    obs = observations.detect_new_52w_low("TEST", prices, lookback_days=5)
    assert obs is None


def test_detect_drawdown_significant() -> None:
    # 260 days at 100, then a big drop.
    prices = _make_prices([100.0] * 260 + [80.0])
    obs = observations.detect_drawdown_significant("TEST", prices, drawdown_pct=15)
    assert obs is not None
    assert obs.metadata["drawdown_pct"] == pytest.approx(20.0, abs=0.1)


def test_detect_drawdown_significant_not_deep_enough() -> None:
    prices = _make_prices([100.0] * 260 + [95.0])  # only 5% drawdown
    obs = observations.detect_drawdown_significant("TEST", prices, drawdown_pct=15)
    assert obs is None


def test_vol_regime_elevated_triggers_on_spike() -> None:
    # 600 calm days then a noisy stretch
    rng = np.random.default_rng(42)
    calm = list(100 + rng.normal(0, 0.1, size=600).cumsum())
    spike = list(calm[-1] + rng.normal(0, 5, size=40).cumsum())
    prices = _make_prices(calm + spike)
    obs = observations.detect_vol_regime_elevated("TEST", prices)
    # We engineered massively higher vol — should fire.
    assert obs is not None


def test_vol_regime_compressed_triggers_on_calm_after_noise() -> None:
    rng = np.random.default_rng(7)
    noisy = list(100 + rng.normal(0, 2, size=600).cumsum())
    calm = list(noisy[-1] + rng.normal(0, 0.01, size=40).cumsum())
    prices = _make_prices(noisy + calm)
    obs = observations.detect_vol_regime_compressed("TEST", prices)
    assert obs is not None


def test_get_active_observations_returns_list() -> None:
    prices = _make_prices([100.0] * 260 + [80.0])
    out = observations.get_active_observations("TEST", prices, benchmark_prices=None)
    types = {o.type for o in out}
    assert "drawdown_significant" in types


def test_get_active_observations_empty_frame() -> None:
    empty = pd.DataFrame(columns=["adj_close"])
    out = observations.get_active_observations("TEST", empty, benchmark_prices=None)
    assert out == []


def test_find_historical_instances_drawdowns() -> None:
    prices = _make_prices([100.0] * 260 + [80.0] + [100.0] * 260 + [70.0])
    dates = observations.find_historical_instances(prices, "drawdown_significant")
    assert len(dates) >= 2


def test_find_historical_instances_unknown_type() -> None:
    prices = _make_prices([100.0] * 260)
    with pytest.raises(ValueError):
        observations.find_historical_instances(prices, "nonexistent_type")
