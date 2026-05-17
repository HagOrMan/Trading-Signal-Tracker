"""Personalized portfolio sanity-check (SPEC §6.5).

Uses real dollar weights (`shares * latest_price`) when shares are available;
falls back to equal-weight + a clear banner otherwise (DEC-012).

All checks follow the same three-part framing as observations: rule_of_thumb,
user_value, what_to_consider — no buy/sell language.
"""
from __future__ import annotations

from dataclasses import dataclass

from src import portfolio as pf

# Sector classification (heuristic — yfinance sector field). When sector is unknown,
# bucket as "Unknown" and report it as such.
SECTOR_CONCENTRATION_LIMIT_PCT = 25.0
SINGLE_NAME_CONCENTRATION_LIMIT_PCT = 10.0
GEO_TARGET_PCT = {"US": 60.0, "CA": 3.0, "INTL": 37.0}
TSX_EXCHANGES = {"TSX"}
US_EXCHANGES = {"NYSE", "NASDAQ", "AMEX", "ARCA"}


@dataclass(frozen=True)
class PortfolioObservation:
    check_name: str
    rule_of_thumb: str
    user_value: str
    benchmark_value: str
    what_to_consider: str
    severity: str  # one of: ok | watch | flag


@dataclass(frozen=True)
class WeightedHolding:
    ticker: str
    exchange: str
    shares: float | None
    latest_price: float | None
    market_value: float | None  # None when shares or price missing
    sector: str | None


def build_weighted_holdings(
    holdings: list[pf.Holding],
    prices: dict[tuple[str, str], float | None],
    sectors: dict[tuple[str, str], str | None],
) -> list[WeightedHolding]:
    """Combine holdings with latest prices + sectors. `prices` and `sectors` are keyed on (ticker, exchange)."""
    out: list[WeightedHolding] = []
    for h in holdings:
        key = (h.ticker, h.exchange)
        price = prices.get(key)
        market_value = None
        if h.shares is not None and price is not None:
            market_value = float(h.shares) * float(price)
        out.append(
            WeightedHolding(
                ticker=h.ticker,
                exchange=h.exchange,
                shares=h.shares,
                latest_price=price,
                market_value=market_value,
                sector=sectors.get(key),
            )
        )
    return out


def has_real_weights(holdings: list[WeightedHolding]) -> bool:
    """True iff every holding has a non-None market value (so weights are real)."""
    if not holdings:
        return False
    return all(h.market_value is not None for h in holdings)


def _weights(holdings: list[WeightedHolding]) -> dict[str, float]:
    """Return a dict of `ticker → weight (0..1)`. Uses dollar weight if available, equal weight otherwise."""
    if not holdings:
        return {}
    if has_real_weights(holdings):
        total = sum(h.market_value for h in holdings if h.market_value is not None)
        if total <= 0:
            return {h.ticker: 0.0 for h in holdings}
        return {h.ticker: (h.market_value or 0.0) / total for h in holdings}
    eq = 1.0 / len(holdings)
    return {h.ticker: eq for h in holdings}


def _geo_bucket(exchange: str) -> str:
    ex = exchange.upper()
    if ex in US_EXCHANGES:
        return "US"
    if ex in TSX_EXCHANGES:
        return "CA"
    return "INTL"


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_sector_concentration(
    holdings: list[WeightedHolding],
) -> PortfolioObservation:
    """Flag if any sector exceeds the 25% rule of thumb."""
    weights = _weights(holdings)
    sector_weights: dict[str, float] = {}
    for h in holdings:
        sector = h.sector or "Unknown"
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weights.get(h.ticker, 0.0)
    if not sector_weights:
        return PortfolioObservation(
            check_name="Sector concentration",
            rule_of_thumb=f"No single sector above {SECTOR_CONCENTRATION_LIMIT_PCT:.0f}%",
            user_value="No holdings",
            benchmark_value="—",
            what_to_consider="Add holdings to see sector exposure.",
            severity="ok",
        )
    top_sector, top_weight = max(sector_weights.items(), key=lambda kv: kv[1])
    severity = "flag" if top_weight * 100 > SECTOR_CONCENTRATION_LIMIT_PCT else "ok"
    user_breakdown = ", ".join(
        f"{s}: {w * 100:.1f}%"
        for s, w in sorted(sector_weights.items(), key=lambda kv: -kv[1])
    )
    return PortfolioObservation(
        check_name="Sector concentration",
        rule_of_thumb=f"No single sector above {SECTOR_CONCENTRATION_LIMIT_PCT:.0f}%",
        user_value=user_breakdown,
        benchmark_value=f"Largest: {top_sector} {top_weight * 100:.1f}%",
        what_to_consider=(
            "Concentrated sector exposure means your portfolio's fate depends "
            "heavily on one industry's cycle. Consider whether this is "
            "intentional (a thesis) or accidental (drift)."
            if severity == "flag"
            else "Sector exposure is within typical diversification guidelines."
        ),
        severity=severity,
    )


def check_geographic_split(
    holdings: list[WeightedHolding],
) -> PortfolioObservation:
    """Compare US / CA / INTL split to global market-cap rule-of-thumb (~60/3/37)."""
    weights = _weights(holdings)
    geo_weights = {"US": 0.0, "CA": 0.0, "INTL": 0.0}
    for h in holdings:
        bucket = _geo_bucket(h.exchange)
        geo_weights[bucket] += weights.get(h.ticker, 0.0)
    if not holdings:
        return PortfolioObservation(
            check_name="Geographic split",
            rule_of_thumb="≈ 60% US / 3% CA / 37% intl (global market-cap weight)",
            user_value="No holdings",
            benchmark_value="—",
            what_to_consider="Add holdings to see geographic exposure.",
            severity="ok",
        )
    # Flag if any bucket differs from target by more than 20pp.
    deltas = {k: (geo_weights[k] * 100) - GEO_TARGET_PCT[k] for k in GEO_TARGET_PCT}
    max_abs_delta = max(abs(d) for d in deltas.values())
    severity = "flag" if max_abs_delta > 20 else ("watch" if max_abs_delta > 10 else "ok")
    user_breakdown = ", ".join(
        f"{k}: {geo_weights[k] * 100:.1f}%" for k in ("US", "CA", "INTL")
    )
    target_breakdown = ", ".join(
        f"{k}: {GEO_TARGET_PCT[k]:.0f}%" for k in ("US", "CA", "INTL")
    )
    if severity == "ok":
        consideration = (
            "Geographic split is in line with global market-cap weights. "
            "Note: this tool buckets by listing exchange, not by underlying revenue."
        )
    else:
        consideration = (
            "Significant home-country or single-region bias. A Canadian investor "
            "might reasonably tilt toward CA for currency/tax reasons; a US-only "
            "investor may want to research international diversification."
        )
    return PortfolioObservation(
        check_name="Geographic split",
        rule_of_thumb="≈ 60% US / 3% CA / 37% intl (global market-cap weight)",
        user_value=user_breakdown,
        benchmark_value=target_breakdown,
        what_to_consider=consideration,
        severity=severity,
    )


def check_single_name_concentration(
    holdings: list[WeightedHolding],
) -> PortfolioObservation:
    """Flag any single ticker that exceeds the 10% rule of thumb."""
    weights = _weights(holdings)
    if not weights:
        return PortfolioObservation(
            check_name="Single-name concentration",
            rule_of_thumb=f"No single ticker above {SINGLE_NAME_CONCENTRATION_LIMIT_PCT:.0f}%",
            user_value="No holdings",
            benchmark_value="—",
            what_to_consider="Add holdings to see single-name concentration.",
            severity="ok",
        )
    largest_ticker, largest_weight = max(weights.items(), key=lambda kv: kv[1])
    over_limit = [
        (t, w)
        for t, w in weights.items()
        if w * 100 > SINGLE_NAME_CONCENTRATION_LIMIT_PCT
    ]
    severity = "flag" if over_limit else "ok"
    if has_real_weights(holdings):
        user_value = ", ".join(
            f"{t}: {w * 100:.1f}%"
            for t, w in sorted(weights.items(), key=lambda kv: -kv[1])[:5]
        )
        benchmark_value = (
            f"Largest: {largest_ticker} {largest_weight * 100:.1f}% "
            f"(based on share counts × latest price)"
        )
    else:
        user_value = (
            f"Equal-weight assumption: {len(weights)} tickers at "
            f"{(1 / len(weights)) * 100:.1f}% each"
        )
        benchmark_value = (
            "No share counts entered — switch on shares column for real weights"
        )
    if severity == "flag":
        consideration = (
            "One or more positions exceed the 10% rule of thumb. Concentrated "
            "positions amplify both upside and downside — make sure this is a "
            "deliberate conviction, not a position that grew through neglect."
        )
    else:
        consideration = (
            "No single position exceeds 10%. If this is a passive index-style "
            "portfolio, that's expected; if it's an active stock portfolio, "
            "concentration may build over time — re-check periodically."
        )
    return PortfolioObservation(
        check_name="Single-name concentration",
        rule_of_thumb=f"No single ticker above {SINGLE_NAME_CONCENTRATION_LIMIT_PCT:.0f}%",
        user_value=user_value,
        benchmark_value=benchmark_value,
        what_to_consider=consideration,
        severity=severity,
    )


def run_all_checks(holdings: list[WeightedHolding]) -> list[PortfolioObservation]:
    """Run every portfolio-level check. Returns a list in display order."""
    return [
        check_sector_concentration(holdings),
        check_geographic_split(holdings),
        check_single_name_concentration(holdings),
    ]
