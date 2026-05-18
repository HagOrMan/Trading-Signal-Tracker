"""Holdings + watchlist management (SPEC §6.1).

Minimal: ticker + exchange + optional shares (DEC-012). Add/remove. That's it.
This is not a tracking tool — share counts only enable the Portfolio Check page.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import portfolio
from src.config import Config
from src.utils import display_ticker

EXCHANGES = ["NYSE", "NASDAQ", "TSX", "AMEX", "ARCA"]


def _render_add_form(table: str) -> None:
    """Inline 'add' form for either 'holdings' or 'watchlist'."""
    with st.form(f"add_{table}_form", clear_on_submit=True):
        cols = st.columns([3, 2, 2, 1])
        with cols[0]:
            ticker = st.text_input("Ticker", key=f"add_{table}_ticker")
        with cols[1]:
            exchange = st.selectbox("Exchange", EXCHANGES, key=f"add_{table}_exchange")
        if table == "holdings":
            with cols[2]:
                shares = st.number_input(
                    "Shares (optional)",
                    min_value=0.0,
                    step=1.0,
                    value=0.0,
                    key=f"add_{table}_shares",
                )
        else:
            shares = None
        with cols[3]:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            submitted = st.form_submit_button("Add", width="stretch")
    if submitted:
        ticker = (ticker or "").strip().upper()
        if not ticker:
            st.error("Ticker is required.")
            return
        if table == "holdings":
            portfolio.add_holding(ticker, exchange, shares=shares or None)
            st.success(f"Added {display_ticker(ticker, exchange)} to holdings.")
        else:
            portfolio.add_to_watchlist(ticker, exchange)
            st.success(f"Added {display_ticker(ticker, exchange)} to watchlist.")
        st.rerun()


def _render_holdings_table() -> None:
    holdings = portfolio.get_holdings()
    if not holdings:
        st.info("No holdings yet. Add tickers above.")
        return
    df = pd.DataFrame(
        [
            {
                "Ticker": h.ticker,
                "Exchange": h.exchange,
                "Shares": h.shares if h.shares is not None else "—",
                "Added": h.added_at[:10],
            }
            for h in holdings
        ]
    )
    st.dataframe(df, hide_index=True, width="stretch")

    with st.expander("Remove a holding"):
        labels = [f"{h.ticker} ({h.exchange})" for h in holdings]
        to_remove = st.selectbox("Select", options=labels, key="remove_holding_pick")
        if st.button("Remove", key="remove_holding_btn"):
            target = holdings[labels.index(to_remove)]
            portfolio.remove_holding(target.ticker, target.exchange)
            st.success(f"Removed {to_remove}.")
            st.rerun()


def _render_watchlist_table() -> None:
    watch = portfolio.get_watchlist()
    if not watch:
        st.info("Watchlist is empty.")
        return
    df = pd.DataFrame(
        [
            {
                "Ticker": w.ticker,
                "Exchange": w.exchange,
                "Added": w.added_at[:10],
            }
            for w in watch
        ]
    )
    st.dataframe(df, hide_index=True, width="stretch")

    with st.expander("Remove from watchlist"):
        labels = [f"{w.ticker} ({w.exchange})" for w in watch]
        to_remove = st.selectbox("Select", options=labels, key="remove_watch_pick")
        if st.button("Remove", key="remove_watch_btn"):
            target = watch[labels.index(to_remove)]
            portfolio.remove_from_watchlist(target.ticker, target.exchange)
            st.success(f"Removed {to_remove}.")
            st.rerun()


def render(config: Config) -> None:
    """Streamlit entry point for Holdings & Watchlist management."""
    st.title("Holdings & Watchlist")
    st.caption(
        "This is a minimal list — the tool uses it to know which tickers you "
        "care about. For full portfolio tracking with cost basis, dividends, "
        "and multi-currency totals, use Sharesight or Empower."
    )

    tab_holdings, tab_watchlist = st.tabs(["Holdings", "Watchlist"])

    with tab_holdings:
        st.markdown("### Add a holding")
        st.caption(
            "Shares are optional but enable real dollar-weight checks on the Portfolio Check page."
        )
        _render_add_form("holdings")
        st.markdown("### Current holdings")
        _render_holdings_table()

    with tab_watchlist:
        st.markdown("### Add to watchlist")
        _render_add_form("watchlist")
        st.markdown("### Current watchlist")
        _render_watchlist_table()
