"""Tests for src.data_fetch — cache behavior, mocked yfinance."""
from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from src import data_fetch


@pytest.fixture
def cache_db(tmp_path):
    path = tmp_path / "cache.db"
    data_fetch.init_cache_db(db_path=path)
    return path


def _fake_yf_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    return pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104],
            "High": [101, 102, 103, 104, 105],
            "Low": [99, 100, 101, 102, 103],
            "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "Adj Close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "Volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=idx,
    )


def test_init_cache_db_idempotent(tmp_path) -> None:
    p = tmp_path / "c.db"
    data_fetch.init_cache_db(db_path=p)
    data_fetch.init_cache_db(db_path=p)


def test_fetch_price_history_writes_to_cache(cache_db) -> None:
    fake_ticker = mock.MagicMock()
    fake_ticker.history.return_value = _fake_yf_frame()
    with mock.patch.object(data_fetch, "yf") as m_yf:
        m_yf.Ticker.return_value = fake_ticker
        df = data_fetch.fetch_price_history("AAPL", db_path=cache_db)
    assert not df.empty
    assert "adj_close" in df.columns
    assert len(df) == 5


def test_fetch_price_history_hits_cache_second_call(cache_db) -> None:
    fake_ticker = mock.MagicMock()
    fake_ticker.history.return_value = _fake_yf_frame()
    with mock.patch.object(data_fetch, "yf") as m_yf:
        m_yf.Ticker.return_value = fake_ticker
        data_fetch.fetch_price_history("AAPL", db_path=cache_db)
        # Second call within the same UTC day should not hit yfinance.
        data_fetch.fetch_price_history("AAPL", db_path=cache_db)
    # yfinance.Ticker should only have been called once (the second was cached).
    assert m_yf.Ticker.call_count == 1


def test_fetch_price_history_network_failure_returns_cached(cache_db) -> None:
    # First, populate the cache via a successful fetch.
    fake_ticker_ok = mock.MagicMock()
    fake_ticker_ok.history.return_value = _fake_yf_frame()
    with mock.patch.object(data_fetch, "yf") as m_yf:
        m_yf.Ticker.return_value = fake_ticker_ok
        data_fetch.fetch_price_history("AAPL", db_path=cache_db)

    # Then a force_refresh that fails — must return cached, not crash.
    fake_ticker_err = mock.MagicMock()
    fake_ticker_err.history.side_effect = ConnectionError("offline")
    with mock.patch.object(data_fetch, "yf") as m_yf:
        m_yf.Ticker.return_value = fake_ticker_err
        df = data_fetch.fetch_price_history(
            "AAPL", db_path=cache_db, force_refresh=True
        )
    assert not df.empty


def test_fetch_price_history_no_yfinance_returns_empty(cache_db) -> None:
    with mock.patch.object(data_fetch, "yf", None):
        df = data_fetch.fetch_price_history("XYZ", db_path=cache_db)
    assert df.empty


def test_get_cache_age_none_for_uncached(cache_db) -> None:
    assert data_fetch.get_cache_age("XYZ", db_path=cache_db) is None


def test_get_latest_price_after_fetch(cache_db) -> None:
    fake_ticker = mock.MagicMock()
    fake_ticker.history.return_value = _fake_yf_frame()
    with mock.patch.object(data_fetch, "yf") as m_yf:
        m_yf.Ticker.return_value = fake_ticker
        data_fetch.fetch_price_history("AAPL", db_path=cache_db)
    assert data_fetch.get_latest_price("AAPL", db_path=cache_db) == 104.5


def test_normalize_yf_frame_handles_missing_adj_close() -> None:
    idx = pd.date_range("2024-01-01", periods=2, freq="B")
    df = pd.DataFrame(
        {"Open": [1, 2], "High": [1, 2], "Low": [1, 2], "Close": [1.5, 2.5], "Volume": [10, 20]},
        index=idx,
    )
    normalized = data_fetch._normalize_yf_frame(df)
    assert "adj_close" in normalized.columns
    # When Adj Close is missing, should fall back to close.
    assert list(normalized["adj_close"]) == [1.5, 2.5]
