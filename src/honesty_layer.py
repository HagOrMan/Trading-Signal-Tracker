"""Per-ticker historical backtest of observations (DEC-009 — show unflattering results unfiltered).

For a given (ticker, observation_type, price_history):
    1. find every historical date the observation would have fired
    2. for each, compute forward returns over 1/3/6/12 month horizons
    3. summarize (count, median, p25, p75, win rate, sample tier)

Cached in `backtest.db`, keyed on (ticker, observation_type, last_data_date).
Cache invalidates automatically when underlying price history extends.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from src import observations
from src.indicators import TRADING_DAYS_PER_MONTH

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "backtest.db"

DEFAULT_HORIZONS = [1, 3, 6, 12]

# DEC-011 sample-size tiers
TIER_LOW = 5
TIER_MODERATE = 15
TIER_GOOD = 30

_SCHEMA = """
CREATE TABLE IF NOT EXISTS backtest_cache (
    ticker            TEXT NOT NULL,
    observation_type  TEXT NOT NULL,
    last_data_date    TEXT NOT NULL,
    horizons_json     TEXT NOT NULL,
    summary_json      TEXT NOT NULL,
    instances_json    TEXT NOT NULL,
    cached_at         TEXT NOT NULL,
    PRIMARY KEY (ticker, observation_type, last_data_date)
);
"""


@contextmanager
def _connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or CACHE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_backtest_db(db_path: Path | str | None = None) -> None:
    """Create the backtest cache table if not present. Idempotent."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


# ---------------------------------------------------------------------------
# Sample size tier
# ---------------------------------------------------------------------------


def sample_tier(n: int) -> str:
    """Map a sample count to one of: very_low | low | moderate | good (DEC-011)."""
    if n < TIER_LOW:
        return "very_low"
    if n < TIER_MODERATE:
        return "low"
    if n < TIER_GOOD:
        return "moderate"
    return "good"


def tier_message(tier: str, n: int) -> str:
    """Human-readable framing of a sample tier — surfaced verbatim in the UI."""
    if tier == "very_low":
        return (
            f"Only {n} historical instances — treat the summary stats below "
            f"as anecdotes, not estimates."
        )
    if tier == "low":
        return (
            f"{n} historical instances — limited statistical confidence."
        )
    if tier == "moderate":
        return (
            f"{n} historical instances — enough for a rough read; outliers "
            f"still move the median."
        )
    return (
        f"{n} historical instances — reasonable sample, but past performance "
        f"does not predict future results."
    )


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def find_historical_instances(
    prices: pd.DataFrame,
    observation_type: str,
    benchmark_prices: pd.DataFrame | None = None,
) -> list[date]:
    """Return all historical dates the observation would have fired. Thin wrapper."""
    return observations.find_historical_instances(
        prices, observation_type, benchmark_prices=benchmark_prices
    )


def forward_returns(
    prices: pd.DataFrame,
    instance_dates: list[date],
    horizons_months: list[int] | None = None,
) -> dict[int, list[float]]:
    """For each horizon, compute forward returns from each instance date.

    Returns a dict mapping horizon (months) → list of forward returns. Instances
    whose horizon falls past the end of price history are skipped silently.
    """
    horizons_months = horizons_months or DEFAULT_HORIZONS
    if prices is None or prices.empty or "adj_close" not in prices.columns:
        return {h: [] for h in horizons_months}

    close = prices["adj_close"].dropna()
    if close.empty:
        return {h: [] for h in horizons_months}

    idx_map = {ts.date(): i for i, ts in enumerate(close.index)}
    out: dict[int, list[float]] = {h: [] for h in horizons_months}
    for d in instance_dates:
        if d not in idx_map:
            # Try the next available trading day for robustness.
            future_idx = close.index.searchsorted(pd.Timestamp(d))
            if future_idx >= len(close):
                continue
            start_idx = int(future_idx)
        else:
            start_idx = idx_map[d]
        start_price = close.iloc[start_idx]
        if pd.isna(start_price) or start_price == 0:
            continue
        for h in horizons_months:
            end_idx = start_idx + h * TRADING_DAYS_PER_MONTH
            if end_idx >= len(close):
                continue
            end_price = close.iloc[end_idx]
            if pd.isna(end_price):
                continue
            out[h].append(float(end_price / start_price - 1.0))
    return out


def summarize_outcomes(
    fwd_returns: dict[int, list[float]],
) -> dict[int, dict]:
    """For each horizon, return summary stats: count, median, p25, p75, win_rate, mean."""
    summary: dict[int, dict] = {}
    for horizon, rets in fwd_returns.items():
        if not rets:
            summary[horizon] = {
                "count": 0,
                "median": None,
                "p25": None,
                "p75": None,
                "win_rate": None,
                "mean": None,
            }
            continue
        arr = np.array(rets, dtype=float)
        summary[horizon] = {
            "count": int(arr.size),
            "median": float(np.median(arr)),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
            "win_rate": float((arr > 0).mean()),
            "mean": float(arr.mean()),
        }
    return summary


# ---------------------------------------------------------------------------
# Public combined entry point + caching
# ---------------------------------------------------------------------------


def _last_data_date(prices: pd.DataFrame) -> str | None:
    if prices is None or prices.empty:
        return None
    return prices.index[-1].date().isoformat()


def _read_cache(
    ticker: str,
    observation_type: str,
    last_data_date: str,
    db_path: Path | str | None = None,
) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT horizons_json, summary_json, instances_json FROM backtest_cache "
            "WHERE ticker = ? AND observation_type = ? AND last_data_date = ?",
            (ticker, observation_type, last_data_date),
        ).fetchone()
    if not row:
        return None
    horizons = json.loads(row["horizons_json"])
    summary_raw = json.loads(row["summary_json"])
    summary = {int(k): v for k, v in summary_raw.items()}
    instances = json.loads(row["instances_json"])
    return {
        "horizons": horizons,
        "summary": summary,
        "instances": instances,
    }


def _write_cache(
    ticker: str,
    observation_type: str,
    last_data_date: str,
    horizons: list[int],
    summary: dict[int, dict],
    instances: list[str],
    db_path: Path | str | None = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO backtest_cache "
            "(ticker, observation_type, last_data_date, horizons_json, "
            " summary_json, instances_json, cached_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(ticker, observation_type, last_data_date) DO UPDATE SET "
            "  horizons_json = excluded.horizons_json, "
            "  summary_json  = excluded.summary_json, "
            "  instances_json = excluded.instances_json, "
            "  cached_at     = excluded.cached_at",
            (
                ticker,
                observation_type,
                last_data_date,
                json.dumps(horizons),
                json.dumps({str(k): v for k, v in summary.items()}),
                json.dumps(instances),
            ),
        )


def backtest_observation(
    ticker: str,
    observation_type: str,
    prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame | None = None,
    horizons_months: list[int] | None = None,
    use_cache: bool = True,
    db_path: Path | str | None = None,
) -> dict:
    """Run (or fetch) the full backtest for one (ticker, observation_type) pair.

    Returns a dict shaped:
        {
          "ticker": str,
          "observation_type": str,
          "instances": [iso-date, ...],
          "horizons": [1, 3, 6, 12],
          "summary": {horizon_int: {count, median, p25, p75, win_rate, mean}, ...},
          "tier": str,
          "tier_message": str,
          "forward_returns": {horizon_int: [float, ...]}   # only when freshly computed
        }
    """
    horizons_months = horizons_months or DEFAULT_HORIZONS
    last_dd = _last_data_date(prices)
    if last_dd is None:
        return {
            "ticker": ticker,
            "observation_type": observation_type,
            "instances": [],
            "horizons": horizons_months,
            "summary": {h: summarize_outcomes({h: []})[h] for h in horizons_months},
            "tier": "very_low",
            "tier_message": tier_message("very_low", 0),
            "forward_returns": {h: [] for h in horizons_months},
        }

    if use_cache:
        cached = _read_cache(ticker, observation_type, last_dd, db_path=db_path)
        if cached and sorted(cached["horizons"]) == sorted(horizons_months):
            n = max((cached["summary"][h]["count"] for h in horizons_months), default=0)
            tier = sample_tier(n)
            return {
                "ticker": ticker,
                "observation_type": observation_type,
                "instances": cached["instances"],
                "horizons": horizons_months,
                "summary": cached["summary"],
                "tier": tier,
                "tier_message": tier_message(tier, n),
                "forward_returns": {h: [] for h in horizons_months},
            }

    instance_dates = find_historical_instances(
        prices, observation_type, benchmark_prices=benchmark_prices
    )
    fwd = forward_returns(prices, instance_dates, horizons_months)
    summary = summarize_outcomes(fwd)
    instances_iso = [d.isoformat() for d in instance_dates]

    if use_cache:
        _write_cache(
            ticker,
            observation_type,
            last_dd,
            horizons_months,
            summary,
            instances_iso,
            db_path=db_path,
        )

    n_total = len(instance_dates)
    tier = sample_tier(n_total)
    return {
        "ticker": ticker,
        "observation_type": observation_type,
        "instances": instances_iso,
        "horizons": horizons_months,
        "summary": summary,
        "tier": tier,
        "tier_message": tier_message(tier, n_total),
        "forward_returns": fwd,
    }
