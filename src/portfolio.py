"""Holdings + watchlist CRUD. SQLite, parameterized queries only.

DEC-010 + DEC-012: holdings store ticker + exchange + optional shares. No cost basis,
no purchase dates — Sharesight/Empower own that.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "portfolio.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL,
    shares REAL,
    added_at TEXT NOT NULL,
    UNIQUE (ticker, exchange)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (ticker, exchange)
);
"""


@dataclass(frozen=True)
class Holding:
    id: int
    ticker: str
    exchange: str
    shares: float | None
    added_at: str


@dataclass(frozen=True)
class WatchEntry:
    id: int
    ticker: str
    exchange: str
    added_at: str


@contextmanager
def _connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection. Caller can pass `:memory:` for tests."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """Create tables if not present. Idempotent."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(ticker: str, exchange: str) -> tuple[str, str]:
    return ticker.strip().upper(), exchange.strip().upper()


def add_holding(
    ticker: str,
    exchange: str,
    shares: float | None = None,
    db_path: Path | str | None = None,
) -> int:
    """Insert (or update shares for) a holding. Returns the row id."""
    ticker, exchange = _norm(ticker, exchange)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO holdings (ticker, exchange, shares, added_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(ticker, exchange) DO UPDATE SET shares = excluded.shares",
            (ticker, exchange, shares, _now()),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM holdings WHERE ticker = ? AND exchange = ?",
            (ticker, exchange),
        ).fetchone()
        return int(row["id"])


def remove_holding(
    ticker: str, exchange: str, db_path: Path | str | None = None
) -> int:
    """Delete a holding. Returns the number of rows deleted (0 or 1)."""
    ticker, exchange = _norm(ticker, exchange)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM holdings WHERE ticker = ? AND exchange = ?",
            (ticker, exchange),
        )
        return cur.rowcount


def get_holdings(db_path: Path | str | None = None) -> list[Holding]:
    """Return all holdings ordered by ticker."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, ticker, exchange, shares, added_at FROM holdings ORDER BY ticker"
        ).fetchall()
    return [
        Holding(
            id=r["id"],
            ticker=r["ticker"],
            exchange=r["exchange"],
            shares=r["shares"],
            added_at=r["added_at"],
        )
        for r in rows
    ]


def update_shares(
    ticker: str,
    exchange: str,
    shares: float | None,
    db_path: Path | str | None = None,
) -> int:
    """Update shares for an existing holding. Returns rows affected."""
    ticker, exchange = _norm(ticker, exchange)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE holdings SET shares = ? WHERE ticker = ? AND exchange = ?",
            (shares, ticker, exchange),
        )
        return cur.rowcount


def add_to_watchlist(
    ticker: str, exchange: str, db_path: Path | str | None = None
) -> int:
    """Insert a ticker into the watchlist. Returns the row id."""
    ticker, exchange = _norm(ticker, exchange)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, exchange, added_at) VALUES (?, ?, ?)",
            (ticker, exchange, _now()),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM watchlist WHERE ticker = ? AND exchange = ?",
            (ticker, exchange),
        ).fetchone()
        return int(row["id"])


def remove_from_watchlist(
    ticker: str, exchange: str, db_path: Path | str | None = None
) -> int:
    """Delete a watchlist entry. Returns rows deleted (0 or 1)."""
    ticker, exchange = _norm(ticker, exchange)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE ticker = ? AND exchange = ?",
            (ticker, exchange),
        )
        return cur.rowcount


def get_watchlist(db_path: Path | str | None = None) -> list[WatchEntry]:
    """Return all watchlist entries ordered by ticker."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, ticker, exchange, added_at FROM watchlist ORDER BY ticker"
        ).fetchall()
    return [
        WatchEntry(
            id=r["id"],
            ticker=r["ticker"],
            exchange=r["exchange"],
            added_at=r["added_at"],
        )
        for r in rows
    ]
