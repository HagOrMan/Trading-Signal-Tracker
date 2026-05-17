"""yfinance wrapper + SQLite price cache.

This is the only module that imports yfinance (DEC-002). Everywhere else calls
through `fetch_price_history()` and gets back a pandas DataFrame.

Network failures must never crash the app — they return an empty frame and a
stale-data signal so views can render a banner.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

try:
    import yfinance as yf
except ImportError:  # pragma: no cover — keeps import-time errors actionable
    yf = None

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker     TEXT NOT NULL,
    date       TEXT NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    adj_close  REAL,
    volume     INTEGER,
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices (ticker);

CREATE TABLE IF NOT EXISTS fetch_meta (
    ticker      TEXT PRIMARY KEY,
    last_fetch  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticker_info (
    ticker      TEXT PRIMARY KEY,
    long_name   TEXT,
    sector      TEXT,
    industry    TEXT,
    country     TEXT,
    currency    TEXT,
    fetched_at  TEXT NOT NULL
);
"""

PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


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


def init_cache_db(db_path: Path | str | None = None) -> None:
    """Create the cache schema if not present. Idempotent."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_cached_prices(ticker: str, db_path: Path | str | None = None) -> pd.DataFrame:
    """Return a DataFrame of cached prices (indexed by date) for `ticker`."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT date, open, high, low, close, adj_close, volume "
            "FROM prices WHERE ticker = ? ORDER BY date",
            (ticker,),
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df[PRICE_COLUMNS]


def _write_prices(
    ticker: str, df: pd.DataFrame, db_path: Path | str | None = None
) -> None:
    """Insert-or-replace rows for `ticker` from a DataFrame indexed by date."""
    if df.empty:
        return
    payload = [
        (
            ticker,
            idx.strftime("%Y-%m-%d"),
            _to_float(row.get("open")),
            _to_float(row.get("high")),
            _to_float(row.get("low")),
            _to_float(row.get("close")),
            _to_float(row.get("adj_close")),
            _to_int(row.get("volume")),
        )
        for idx, row in df.iterrows()
    ]
    with _connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO prices (ticker, date, open, high, low, close, adj_close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker, date) DO UPDATE SET "
            "  open=excluded.open, high=excluded.high, low=excluded.low, "
            "  close=excluded.close, adj_close=excluded.adj_close, volume=excluded.volume",
            payload,
        )
        conn.execute(
            "INSERT INTO fetch_meta (ticker, last_fetch) VALUES (?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET last_fetch = excluded.last_fetch",
            (ticker, _now_iso()),
        )


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def get_cache_age(ticker: str, db_path: Path | str | None = None) -> int | None:
    """Return age in seconds since last fetch for `ticker`. None if never fetched."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT last_fetch FROM fetch_meta WHERE ticker = ?", (ticker,)
        ).fetchone()
    if not row:
        return None
    last = datetime.fromisoformat(row["last_fetch"])
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - last
    return int(delta.total_seconds())


def _cache_is_fresh(ticker: str, db_path: Path | str | None = None) -> bool:
    """A cache entry from the current UTC day is considered fresh."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT last_fetch FROM fetch_meta WHERE ticker = ?", (ticker,)
        ).fetchone()
    if not row:
        return False
    last = datetime.fromisoformat(row["last_fetch"])
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last.date() == datetime.now(timezone.utc).date()


def _normalize_yf_frame(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance returns mixed-case columns including 'Adj Close'. Normalize."""
    if df is None or df.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    # yfinance sometimes returns MultiIndex columns when group_by="ticker" or for
    # multi-ticker frames. Flatten to the first level just in case.
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    rename = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename)
    # If "adj_close" is missing (newer yfinance returns auto-adjusted "close" only),
    # fall back to the close column. That keeps DEC-006 honored — yfinance's
    # auto_adjust=True default already applies splits/dividends to "close".
    if "adj_close" not in df.columns and "close" in df.columns:
        df["adj_close"] = df["close"]
    for col in PRICE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[PRICE_COLUMNS]
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df.sort_index()


def fetch_price_history(
    ticker: str,
    period: str = "max",
    force_refresh: bool = False,
    db_path: Path | str | None = None,
) -> pd.DataFrame:
    """Return adjusted price history for `ticker`. Cache-first.

    Returns an empty DataFrame on network failure (logged at WARNING). Callers
    decide what to render — typically a stale-data banner.
    """
    cached = _read_cached_prices(ticker, db_path=db_path)
    if (
        not force_refresh
        and not cached.empty
        and _cache_is_fresh(ticker, db_path=db_path)
    ):
        return cached

    if yf is None:
        logger.warning("yfinance not installed; returning cached data for %s", ticker)
        return cached

    try:
        # auto_adjust=False keeps the explicit "Adj Close" column when available.
        # Some yfinance versions ignore this; _normalize_yf_frame handles both shapes.
        raw = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    except Exception as exc:  # noqa: BLE001 — network/parse errors are all best-effort
        logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
        return cached

    fresh = _normalize_yf_frame(raw)
    if fresh.empty:
        logger.warning("yfinance returned no data for %s", ticker)
        return cached

    _write_prices(ticker, fresh, db_path=db_path)
    return _read_cached_prices(ticker, db_path=db_path)


def fetch_ticker_info(ticker: str, db_path: Path | str | None = None) -> dict:
    """Return basic info (long_name, sector, industry, currency). {} on failure."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT long_name, sector, industry, country, currency FROM ticker_info "
            "WHERE ticker = ?",
            (ticker,),
        ).fetchone()
    if row:
        return {k: row[k] for k in row.keys() if row[k] is not None}

    if yf is None:
        return {}

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("yfinance info fetch failed for %s: %s", ticker, exc)
        return {}

    record = {
        "long_name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "currency": info.get("currency"),
    }
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO ticker_info (ticker, long_name, sector, industry, country, currency, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET long_name=excluded.long_name, "
            "  sector=excluded.sector, industry=excluded.industry, "
            "  country=excluded.country, currency=excluded.currency, "
            "  fetched_at=excluded.fetched_at",
            (
                ticker,
                record["long_name"],
                record["sector"],
                record["industry"],
                record["country"],
                record["currency"],
                _now_iso(),
            ),
        )
    return {k: v for k, v in record.items() if v is not None}


def get_latest_price(ticker: str, db_path: Path | str | None = None) -> float | None:
    """Convenience: return the most recent adj_close in cache. None if absent."""
    df = _read_cached_prices(ticker, db_path=db_path)
    if df.empty:
        return None
    val = df["adj_close"].iloc[-1]
    if pd.isna(val):
        return None
    return float(val)
