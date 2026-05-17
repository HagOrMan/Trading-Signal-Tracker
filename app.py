"""Anti-Signal Tool — Streamlit entry point.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import logging

import streamlit as st

from src import data_fetch, honesty_layer, portfolio
from src.checklist import init_decisions_db
from src.config import load_config
from src.views import holdings, journal, portfolio_check, ticker_review

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


DISCLAIMER = (
    "This tool is for personal informational use only and does not constitute "
    "financial advice.\n\n"
    "Observations are data patterns worth researching — not buy/sell "
    "recommendations.\n\n"
    "The honesty layer shows historical patterns on a single ticker; past "
    "performance does not predict future results.\n\n"
    "Market data is end-of-day and may be delayed.\n\n"
    "For full portfolio tracking and charting, use **Sharesight**, **Empower**, "
    "or **Yahoo Finance**."
)


PAGES = {
    "Review a ticker": ticker_review.render,
    "Holdings & watchlist": holdings.render,
    "Portfolio check": portfolio_check.render,
    "Decision journal": journal.render,
}


@st.cache_resource
def _bootstrap_databases() -> None:
    """Create all SQLite schemas once per process. Idempotent."""
    portfolio.init_db()
    data_fetch.init_cache_db()
    honesty_layer.init_backtest_db()
    init_decisions_db()


@st.cache_resource
def _load_config_cached():
    return load_config()


def main() -> None:
    st.set_page_config(
        page_title="Anti-Signal Tool",
        page_icon="🐢",
        layout="wide",
    )
    _bootstrap_databases()
    config = _load_config_cached()

    with st.sidebar:
        st.title("🐢 Anti-Signal Tool")
        st.caption(
            "A decision speed bump with a built-in honesty layer. Open it "
            "before you act, not while you watch."
        )
        page = st.radio("Page", list(PAGES.keys()), label_visibility="collapsed")

        st.markdown("---")
        with st.expander("About this tool", expanded=False):
            st.markdown(
                "Built for the moment *before pulling the trigger* on an "
                "investment decision. It is **not** a portfolio dashboard, "
                "a charting tool, or a signal generator. "
                "For those, keep using Yahoo Finance, Empower, Sharesight, "
                "or Finviz — they do those jobs well."
            )
        st.markdown("---")
        st.caption(DISCLAIMER)

    PAGES[page](config)


if __name__ == "__main__":
    main()
