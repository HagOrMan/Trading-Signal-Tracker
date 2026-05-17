"""Shared helpers: ticker normalization, formatting."""
from __future__ import annotations

VALID_EXCHANGES = {"NYSE", "NASDAQ", "TSX", "AMEX", "ARCA"}


def normalize_ticker(ticker: str, exchange: str) -> str:
    """Return the yfinance symbol for a (ticker, exchange) pair.

    TSX tickers get a `.TO` suffix unless already present. US exchanges pass through.
    Raises ValueError on unknown exchange.
    """
    if not ticker or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")
    ticker = ticker.strip().upper()
    exchange = (exchange or "").strip().upper()

    if exchange not in VALID_EXCHANGES:
        raise ValueError(
            f"unknown exchange {exchange!r}; expected one of {sorted(VALID_EXCHANGES)}"
        )

    if exchange == "TSX":
        return ticker if ticker.endswith(".TO") else f"{ticker}.TO"
    return ticker


def display_ticker(ticker: str, exchange: str) -> str:
    """Return a user-facing label like `RY (TSX)` regardless of suffix."""
    bare = ticker.removesuffix(".TO").upper()
    return f"{bare} ({exchange.upper()})"


def format_pct(value: float, decimals: int = 2) -> str:
    """Format a fraction (0.0532) as a percent string (`+5.32%`). NaN → `n/a`."""
    if value is None:
        return "n/a"
    try:
        if value != value:  # NaN check without importing math
            return "n/a"
    except TypeError:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value * 100:.{decimals}f}%"


def format_currency(value: float, currency: str = "USD", decimals: int = 2) -> str:
    """Format a numeric amount with a currency code suffix. NaN → `n/a`."""
    if value is None:
        return "n/a"
    try:
        if value != value:
            return "n/a"
    except TypeError:
        return "n/a"
    return f"{value:,.{decimals}f} {currency.upper()}"


def format_count(n: int | None) -> str:
    """Format an integer count, with `0` and `None` rendered as `0` and `n/a`."""
    if n is None:
        return "n/a"
    return f"{n:,}"
