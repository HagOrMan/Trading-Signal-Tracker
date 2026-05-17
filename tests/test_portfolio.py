"""Tests for src.portfolio — CRUD round-trip with a temp SQLite file."""
from __future__ import annotations

import pytest

from src import portfolio


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "portfolio.db"
    portfolio.init_db(db_path=path)
    return path


def test_init_db_idempotent(tmp_path) -> None:
    path = tmp_path / "p.db"
    portfolio.init_db(db_path=path)
    portfolio.init_db(db_path=path)  # second call must not raise
    assert path.exists()


def test_add_and_get_holding(db) -> None:
    portfolio.add_holding("AAPL", "NYSE", shares=10.0, db_path=db)
    holdings = portfolio.get_holdings(db_path=db)
    assert len(holdings) == 1
    assert holdings[0].ticker == "AAPL"
    assert holdings[0].exchange == "NYSE"
    assert holdings[0].shares == 10.0


def test_add_holding_no_shares(db) -> None:
    portfolio.add_holding("AAPL", "NYSE", db_path=db)
    holdings = portfolio.get_holdings(db_path=db)
    assert holdings[0].shares is None


def test_add_holding_upserts_shares(db) -> None:
    portfolio.add_holding("AAPL", "NYSE", shares=5.0, db_path=db)
    portfolio.add_holding("AAPL", "NYSE", shares=15.0, db_path=db)
    holdings = portfolio.get_holdings(db_path=db)
    assert len(holdings) == 1
    assert holdings[0].shares == 15.0


def test_remove_holding(db) -> None:
    portfolio.add_holding("AAPL", "NYSE", db_path=db)
    deleted = portfolio.remove_holding("AAPL", "NYSE", db_path=db)
    assert deleted == 1
    assert portfolio.get_holdings(db_path=db) == []


def test_remove_nonexistent_holding(db) -> None:
    deleted = portfolio.remove_holding("XYZ", "NYSE", db_path=db)
    assert deleted == 0


def test_update_shares(db) -> None:
    portfolio.add_holding("AAPL", "NYSE", shares=5.0, db_path=db)
    portfolio.update_shares("AAPL", "NYSE", 42.0, db_path=db)
    holdings = portfolio.get_holdings(db_path=db)
    assert holdings[0].shares == 42.0


def test_watchlist_round_trip(db) -> None:
    portfolio.add_to_watchlist("MSFT", "NASDAQ", db_path=db)
    portfolio.add_to_watchlist("RY", "TSX", db_path=db)
    watch = portfolio.get_watchlist(db_path=db)
    assert {(w.ticker, w.exchange) for w in watch} == {("MSFT", "NASDAQ"), ("RY", "TSX")}

    portfolio.remove_from_watchlist("MSFT", "NASDAQ", db_path=db)
    watch = portfolio.get_watchlist(db_path=db)
    assert len(watch) == 1
    assert watch[0].ticker == "RY"


def test_holdings_unique_per_ticker_exchange(db) -> None:
    portfolio.add_holding("AAPL", "NYSE", db_path=db)
    portfolio.add_holding("AAPL", "NYSE", db_path=db)
    holdings = portfolio.get_holdings(db_path=db)
    assert len(holdings) == 1
