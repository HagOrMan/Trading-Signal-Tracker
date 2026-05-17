"""Tests for src.utils."""
from __future__ import annotations

import math

import pytest

from src import utils


def test_normalize_ticker_us_passthrough() -> None:
    assert utils.normalize_ticker("AAPL", "NYSE") == "AAPL"
    assert utils.normalize_ticker("aapl", "nasdaq") == "AAPL"


def test_normalize_ticker_tsx_adds_suffix() -> None:
    assert utils.normalize_ticker("RY", "TSX") == "RY.TO"
    assert utils.normalize_ticker("SHOP", "TSX") == "SHOP.TO"


def test_normalize_ticker_tsx_idempotent() -> None:
    assert utils.normalize_ticker("RY.TO", "TSX") == "RY.TO"


def test_normalize_ticker_blank_raises() -> None:
    with pytest.raises(ValueError):
        utils.normalize_ticker("", "NYSE")


def test_normalize_ticker_unknown_exchange_raises() -> None:
    with pytest.raises(ValueError):
        utils.normalize_ticker("RY", "LSE")


def test_format_pct_basic() -> None:
    assert utils.format_pct(0.0532) == "+5.32%"
    assert utils.format_pct(-0.10) == "-10.00%"
    assert utils.format_pct(0.0) == "0.00%"


def test_format_pct_nan() -> None:
    assert utils.format_pct(float("nan")) == "n/a"
    assert utils.format_pct(None) == "n/a"


def test_format_pct_custom_decimals() -> None:
    assert utils.format_pct(0.1, decimals=1) == "+10.0%"


def test_format_currency_basic() -> None:
    assert utils.format_currency(1234.5, "USD") == "1,234.50 USD"
    assert utils.format_currency(0, "CAD") == "0.00 CAD"


def test_format_currency_nan() -> None:
    assert utils.format_currency(float("nan")) == "n/a"
    assert utils.format_currency(None) == "n/a"


def test_display_ticker_tsx_strips_suffix() -> None:
    assert utils.display_ticker("RY.TO", "TSX") == "RY (TSX)"
    assert utils.display_ticker("RY", "TSX") == "RY (TSX)"


def test_format_count() -> None:
    assert utils.format_count(1234) == "1,234"
    assert utils.format_count(0) == "0"
    assert utils.format_count(None) == "n/a"
