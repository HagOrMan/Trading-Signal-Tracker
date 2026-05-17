"""Portfolio sanity-check page (SPEC §6.5).

Reads holdings, fetches latest prices + sectors (cache-first), runs the three
checks defined in `advice.py`, renders each as an observation-style card.

Explicit banner: this is not a tracking tool.
"""
from __future__ import annotations

import streamlit as st

from src import advice, data_fetch, portfolio
from src.config import Config
from src.utils import normalize_ticker

SEVERITY_ICON = {"ok": "🟢", "watch": "🟡", "flag": "🔴"}


@st.cache_data(ttl=3600, show_spinner=False)
def _latest_price(symbol: str) -> float | None:
    return data_fetch.get_latest_price(symbol)


@st.cache_data(ttl=3600, show_spinner=False)
def _info(symbol: str) -> dict:
    return data_fetch.fetch_ticker_info(symbol)


def _hydrate_holdings(holdings: list[portfolio.Holding]) -> list[advice.WeightedHolding]:
    """Fetch latest prices and sectors for each holding (cache-first)."""
    prices: dict[tuple[str, str], float | None] = {}
    sectors: dict[tuple[str, str], str | None] = {}
    for h in holdings:
        try:
            symbol = normalize_ticker(h.ticker, h.exchange)
        except ValueError:
            continue
        # Trigger a refresh if no cached prices exist at all — but don't refetch
        # on every load since the cache layer handles freshness.
        if data_fetch.get_latest_price(symbol) is None:
            data_fetch.fetch_price_history(symbol, period="1y")
        prices[(h.ticker, h.exchange)] = _latest_price(symbol)
        info = _info(symbol)
        sectors[(h.ticker, h.exchange)] = info.get("sector")
    return advice.build_weighted_holdings(holdings, prices, sectors)


def _render_check_card(obs: advice.PortfolioObservation) -> None:
    icon = SEVERITY_ICON.get(obs.severity, "⬜")
    with st.container(border=True):
        st.markdown(f"#### {icon} {obs.check_name}")
        cols = st.columns([1, 1])
        with cols[0]:
            st.markdown(f"**Rule of thumb:** {obs.rule_of_thumb}")
            st.markdown(f"**Your portfolio:** {obs.user_value}")
        with cols[1]:
            st.markdown(f"**Benchmark / detail:** {obs.benchmark_value}")
            st.markdown(f"**Severity:** `{obs.severity}`")
        st.markdown(f"**What to consider:** {obs.what_to_consider}")


def render(config: Config) -> None:
    """Streamlit entry point for the Portfolio Check page."""
    st.title("Portfolio sanity check")
    st.info(
        "This is a quick sanity check, not a tracking tool. For full portfolio "
        "tracking with multi-currency, dividends, and tax reporting, use "
        "**Sharesight** or **Empower**.",
        icon="ℹ️",
    )

    holdings = portfolio.get_holdings()
    if not holdings:
        st.warning("Add holdings on the Holdings page to run the portfolio check.")
        return

    with st.spinner("Pricing your holdings…"):
        weighted = _hydrate_holdings(holdings)

    if advice.has_real_weights(weighted):
        st.success(
            "All holdings have shares entered — checks are using real dollar weights.",
            icon="✅",
        )
    else:
        missing = [
            f"{h.ticker} ({h.exchange})"
            for h in weighted
            if h.market_value is None
        ]
        st.warning(
            "Some holdings are missing shares — the checks below use an "
            "**equal-weight assumption**. Add shares on the Holdings page for "
            "accurate dollar-weighted concentration metrics.\n\n"
            f"Missing shares: {', '.join(missing)}",
            icon="⚠️",
        )

    for check in advice.run_all_checks(weighted):
        _render_check_card(check)

    st.markdown("---")
    st.caption(
        "Reminder: this tool intentionally ignores bonds, cash, and "
        "non-equity assets. Concentration metrics are equity-only."
    )
