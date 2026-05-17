"""Tests for src.advice — portfolio sanity checks."""
from __future__ import annotations

from src import advice
from src.portfolio import Holding


def _h(ticker: str, exchange: str, shares: float | None = None) -> Holding:
    return Holding(
        id=0, ticker=ticker, exchange=exchange, shares=shares, added_at="2026-01-01T00:00:00Z"
    )


def test_has_real_weights_true_only_when_all_have_values() -> None:
    a = advice.WeightedHolding("A", "NYSE", 1.0, 10.0, 10.0, "Tech")
    b = advice.WeightedHolding("B", "NYSE", None, 10.0, None, "Tech")
    assert advice.has_real_weights([a]) is True
    assert advice.has_real_weights([a, b]) is False
    assert advice.has_real_weights([]) is False


def test_sector_concentration_flag_when_one_sector_dominates() -> None:
    h = [
        advice.WeightedHolding("A", "NYSE", 1.0, 100.0, 100.0, "Tech"),
        advice.WeightedHolding("B", "NYSE", 1.0, 100.0, 100.0, "Tech"),
        advice.WeightedHolding("C", "NYSE", 1.0, 100.0, 100.0, "Tech"),
        advice.WeightedHolding("D", "NYSE", 1.0, 100.0, 100.0, "Energy"),
    ]
    obs = advice.check_sector_concentration(h)
    assert obs.severity == "flag"
    assert "Tech" in obs.benchmark_value


def test_sector_concentration_ok_when_diversified() -> None:
    h = [
        advice.WeightedHolding(t, "NYSE", 1.0, 100.0, 100.0, sector)
        for t, sector in [
            ("A", "Tech"), ("B", "Energy"), ("C", "Healthcare"),
            ("D", "Financials"), ("E", "Consumer"),
        ]
    ]
    obs = advice.check_sector_concentration(h)
    assert obs.severity == "ok"


def test_geographic_split_flag_when_all_canadian() -> None:
    h = [advice.WeightedHolding("RY", "TSX", 1.0, 100.0, 100.0, "Financials")]
    obs = advice.check_geographic_split(h)
    assert obs.severity == "flag"


def test_geographic_split_ok_when_roughly_global() -> None:
    # Approx 60% US, 3% CA, 37% intl by count — using equal-weight here means
    # we need the right number of holdings in each bucket. Use real weights instead.
    us = [
        advice.WeightedHolding(f"U{i}", "NYSE", 1.0, 60.0, 60.0, "Tech")
        for i in range(1)
    ]
    ca = [advice.WeightedHolding("RY", "TSX", 1.0, 3.0, 3.0, "Fin")]
    intl = [advice.WeightedHolding("INT", "LSE", 1.0, 37.0, 37.0, "Tech")]
    obs = advice.check_geographic_split(us + ca + intl)
    assert obs.severity == "ok"


def test_single_name_concentration_flag() -> None:
    # One holding dominates by dollar value.
    h = [
        advice.WeightedHolding("BIG", "NYSE", 100.0, 100.0, 10000.0, "Tech"),
        advice.WeightedHolding("SM1", "NYSE", 1.0, 100.0, 100.0, "Tech"),
        advice.WeightedHolding("SM2", "NYSE", 1.0, 100.0, 100.0, "Tech"),
    ]
    obs = advice.check_single_name_concentration(h)
    assert obs.severity == "flag"


def test_single_name_concentration_equal_weight_path() -> None:
    # No shares → equal weight; with N >= 11, equal weight < 10% so no flag.
    h = [
        advice.WeightedHolding(f"T{i}", "NYSE", None, None, None, "Tech")
        for i in range(11)
    ]
    obs = advice.check_single_name_concentration(h)
    assert obs.severity == "ok"
    assert "Equal-weight" in obs.user_value


def test_run_all_checks_returns_three() -> None:
    h = [advice.WeightedHolding("A", "NYSE", 1.0, 100.0, 100.0, "Tech")]
    out = advice.run_all_checks(h)
    assert len(out) == 3


def test_build_weighted_holdings_threads_prices_and_sectors() -> None:
    holdings = [_h("AAPL", "NYSE", shares=10.0), _h("RY", "TSX")]
    prices = {("AAPL", "NYSE"): 200.0, ("RY", "TSX"): 130.0}
    sectors = {("AAPL", "NYSE"): "Tech", ("RY", "TSX"): "Financials"}
    out = advice.build_weighted_holdings(holdings, prices, sectors)
    assert out[0].market_value == 2000.0
    assert out[1].market_value is None  # no shares
    assert out[1].sector == "Financials"
