"""Tests for src.honesty_layer — synthetic ticker with engineered instances.

These verify the honesty-layer math is honest (DEC-009) — negative outcomes
must surface as negative numbers in the summary.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src import honesty_layer


def _series(values: list[float], start: str = "2018-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.DataFrame({"adj_close": values}, index=idx)


def test_sample_tier_thresholds() -> None:
    assert honesty_layer.sample_tier(0) == "very_low"
    assert honesty_layer.sample_tier(4) == "very_low"
    assert honesty_layer.sample_tier(5) == "low"
    assert honesty_layer.sample_tier(14) == "low"
    assert honesty_layer.sample_tier(15) == "moderate"
    assert honesty_layer.sample_tier(29) == "moderate"
    assert honesty_layer.sample_tier(30) == "good"
    assert honesty_layer.sample_tier(1000) == "good"


def test_tier_message_distinct_per_tier() -> None:
    msgs = {honesty_layer.tier_message(t, 10) for t in ("very_low", "low", "moderate", "good")}
    assert len(msgs) == 4


def test_forward_returns_known_outcomes() -> None:
    # Simple step-up series — every horizon of 1 month from anywhere should be +X%.
    values = [100.0 * (1.01 ** i) for i in range(600)]  # 1% per business day
    prices = _series(values)
    instance = prices.index[10].date()
    fwd = honesty_layer.forward_returns(prices, [instance], horizons_months=[1])
    assert len(fwd[1]) == 1
    # 1% per business day, 21 days ≈ (1.01)^21 ≈ 1.232 → ~23.2%
    assert fwd[1][0] == pytest.approx((1.01 ** 21) - 1.0, rel=1e-6)


def test_forward_returns_skips_out_of_bounds() -> None:
    values = [100.0] * 30
    prices = _series(values)
    # Instance near end can't compute 6-month forward return.
    instance = prices.index[-2].date()
    fwd = honesty_layer.forward_returns(prices, [instance], horizons_months=[6])
    assert fwd[6] == []


def test_forward_returns_negative_outcome_surfaces() -> None:
    # 200 flat days at 100, then 200 days crashed to 50.
    values = [100.0] * 200 + [50.0] * 200
    prices = _series(values)
    # Instance at idx 150 (still flat). 6-month horizon = 126 trading days → idx 276
    # (crashed region). Forward return must be -0.5.
    instance = prices.index[150].date()
    fwd = honesty_layer.forward_returns(prices, [instance], horizons_months=[6])
    assert len(fwd[6]) == 1
    assert fwd[6][0] == pytest.approx(-0.5)  # honesty: negative outcomes must surface


def test_summarize_outcomes_basic_stats() -> None:
    fwd = {1: [0.1, 0.2, -0.05, 0.0, 0.5]}
    summary = honesty_layer.summarize_outcomes(fwd)
    assert summary[1]["count"] == 5
    assert summary[1]["median"] == pytest.approx(0.1)
    assert summary[1]["win_rate"] == pytest.approx(3 / 5)
    assert summary[1]["mean"] == pytest.approx(0.15)


def test_summarize_outcomes_empty() -> None:
    summary = honesty_layer.summarize_outcomes({1: [], 3: []})
    assert summary[1]["count"] == 0
    assert summary[1]["median"] is None
    assert summary[1]["win_rate"] is None


def test_backtest_observation_cache_round_trip(tmp_path) -> None:
    # Create a synthetic ticker with engineered drawdown instances.
    rng = np.random.default_rng(0)
    values = list(100 + rng.normal(0, 0.5, size=1000).cumsum())
    prices = _series(values)
    db = tmp_path / "backtest.db"
    honesty_layer.init_backtest_db(db_path=db)

    r1 = honesty_layer.backtest_observation(
        ticker="TEST",
        observation_type="drawdown_significant",
        prices=prices,
        db_path=db,
    )
    assert r1["tier"] in {"very_low", "low", "moderate", "good"}

    # Second call hits cache — should not recompute (no forward_returns payload).
    r2 = honesty_layer.backtest_observation(
        ticker="TEST",
        observation_type="drawdown_significant",
        prices=prices,
        db_path=db,
    )
    assert r2["summary"] == r1["summary"]


def test_backtest_observation_handles_empty_prices() -> None:
    empty = pd.DataFrame(columns=["adj_close"])
    r = honesty_layer.backtest_observation(
        ticker="TEST",
        observation_type="drawdown_significant",
        prices=empty,
        use_cache=False,
    )
    assert r["tier"] == "very_low"
    assert r["instances"] == []
