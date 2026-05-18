"""Decision journal review (SPEC §6.4 — the self-review tab).

Tabs:
    - Recent (last 30 days)
    - Old enough to review (>6 months old)
    - All entries
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import checklist as cl
from src import data_fetch
from src.config import Config
from src.utils import format_pct, normalize_ticker


def _current_price(ticker: str, exchange: str) -> float | None:
    """Cheap helper: read latest cached price; do not refetch on the journal page."""
    try:
        symbol = normalize_ticker(ticker, exchange)
    except ValueError:
        return None
    return data_fetch.get_latest_price(symbol)


def _render_entry(entry: cl.JournalEntry) -> None:
    """One journal entry as a bordered card with context + return-since."""
    with st.container(border=True):
        cols = st.columns([2, 1, 1, 1])
        with cols[0]:
            st.markdown(f"**{entry.ticker} ({entry.exchange})**")
            st.caption(f"Logged: {entry.date[:19].replace('T', ' ')} UTC")
        with cols[1]:
            st.markdown(f"**Action:** `{entry.action_planned}`")
        with cols[2]:
            price = _current_price(entry.ticker, entry.exchange)
            if entry.price_at_decision and price:
                ret = price / entry.price_at_decision - 1.0
                st.markdown(f"**Since:** {format_pct(ret)}")
                st.caption(f"{entry.price_at_decision:.2f} → {price:.2f}")
            else:
                st.markdown("**Since:** n/a")
        with cols[3]:
            n_obs = len(entry.active_observations)
            st.markdown(f"**Obs at time:** {n_obs}")

        st.markdown(f"> {entry.decision_note}")

        with st.expander("Checklist state at time of decision"):
            for item, checked in entry.checklist_state.items():
                mark = "✅" if checked else "⬜"
                st.markdown(f"{mark} {item}")

        if entry.active_observations:
            with st.expander("Observations active at the time"):
                for obs in entry.active_observations:
                    obs_type = obs.get("type", "unknown")
                    headline = obs.get("headline", "(no headline)")
                    what_happened = obs.get("what_happened", "")
                    st.markdown(f"- **{obs_type}** — {headline}")
                    if what_happened:
                        st.caption(what_happened)


def _entries_to_df(entries: list[cl.JournalEntry]) -> pd.DataFrame:
    """Compact tabular view of entries (for sorting)."""
    rows = []
    for e in entries:
        price_now = _current_price(e.ticker, e.exchange)
        ret = (
            (price_now / e.price_at_decision - 1.0)
            if e.price_at_decision and price_now
            else None
        )
        rows.append(
            {
                "Date": e.date[:10],
                "Ticker": f"{e.ticker} ({e.exchange})",
                "Action": e.action_planned,
                "Price@decision": e.price_at_decision,
                "Price now": price_now,
                "Return": ret,
                "Obs count": len(e.active_observations),
                "Note": (
                    (e.decision_note[:80] + "…")
                    if len(e.decision_note) > 80
                    else e.decision_note
                ),
            }
        )
    return pd.DataFrame(rows)


def render(config: Config) -> None:
    """Streamlit entry point for the Journal page."""
    st.title("Decision journal")
    st.caption(
        "Every entry is a snapshot of what you were thinking, what observations "
        "were active, and what you planned to do. Re-read these to evaluate "
        "your own judgment over time."
    )

    all_entries = cl.get_all_entries()
    if not all_entries:
        st.info(
            "No journal entries yet. Open a ticker, click 'I'm considering "
            "acting on this', and save your first entry."
        )
        return

    tab_recent, tab_old, tab_all = st.tabs(
        ["Recent (30d)", "Old enough to review (>6mo)", "All entries"]
    )

    with tab_recent:
        recent = cl.get_entries_within_days(30)
        if not recent:
            st.info("No entries in the last 30 days.")
        else:
            for e in recent:
                _render_entry(e)

    with tab_old:
        old = cl.get_entries_older_than(6)
        if not old:
            st.info(
                "No entries are >6 months old yet. Come back later — the point "
                "is to re-read past decisions against actual outcomes."
            )
        else:
            st.caption(
                f"{len(old)} entries are at least 6 months old. Re-read each "
                "and ask: was the reasoning sound? Did the observation matter?"
            )
            for e in old:
                _render_entry(e)

    with tab_all:
        st.markdown(f"### {len(all_entries)} total entries")
        df = _entries_to_df(all_entries)
        st.dataframe(df, hide_index=True, width="stretch")
