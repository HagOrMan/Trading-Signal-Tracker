"""The main view (SPEC §7 step 2-4).

Layout:
    1. Ticker input row (text + exchange selector)
    2. Per-observation card: framing text + honesty-layer panel
    3. "I'm considering acting on this" button → checklist + journal modal
"""

from __future__ import annotations

import logging
from dataclasses import asdict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import checklist as cl
from src import data_fetch, honesty_layer, observations
from src.config import Config
from src.utils import display_ticker, format_pct, normalize_ticker

logger = logging.getLogger(__name__)

EXCHANGES = ["NYSE", "NASDAQ", "TSX", "AMEX", "ARCA"]


DISCLAIMER_SHORT = (
    "These are observations — data patterns worth researching, not buy/sell "
    "recommendations. Past performance does not predict future results."
)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_fetch(symbol: str) -> pd.DataFrame:
    return data_fetch.fetch_price_history(symbol, period="max")


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_info(symbol: str) -> dict:
    return data_fetch.fetch_ticker_info(symbol)


def _staleness_banner(symbol: str) -> None:
    age = data_fetch.get_cache_age(symbol)
    if age is None:
        st.caption("No cached data yet — fetching from yfinance.")
        return
    hours = age / 3600
    if hours > 24:
        st.warning(
            f"Cached data is {hours:.1f} hours old. Refresh to fetch the latest "
            f"close (network permitting).",
            icon="⚠️",
        )


def _render_honesty_panel(
    ticker: str,
    obs_type: str,
    prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame | None,
    config: Config,
) -> None:
    """Render the honesty-layer panel below an observation card."""
    result = honesty_layer.backtest_observation(
        ticker=ticker,
        observation_type=obs_type,
        prices=prices,
        benchmark_prices=benchmark_prices,
        horizons_months=config.honesty_layer.forward_horizons_months,
    )
    st.markdown(f"##### Honesty layer — what happened next, historically, on {ticker}")
    n_total = len(result["instances"])
    tier_color = {
        "very_low": "🟥",
        "low": "🟧",
        "moderate": "🟨",
        "good": "🟩",
    }.get(result["tier"], "⬜")
    st.markdown(
        f"{tier_color} **Sample tier:** `{result['tier']}` — {result['tier_message']}"
    )

    if n_total == 0:
        st.info(
            f"This observation has never fired on {ticker} historically. "
            "That's a meaningful piece of context — there is no per-ticker base rate to anchor on."
        )
        return

    summary = result["summary"]
    table_rows = []
    for h in sorted(summary.keys()):
        s = summary[h]
        table_rows.append(
            {
                "Horizon": f"{h} mo",
                "N": s["count"],
                "Median": format_pct(s["median"]) if s["median"] is not None else "n/a",
                "p25": format_pct(s["p25"]) if s["p25"] is not None else "n/a",
                "p75": format_pct(s["p75"]) if s["p75"] is not None else "n/a",
                "Win rate": (
                    format_pct(s["win_rate"]) if s["win_rate"] is not None else "n/a"
                ),
            }
        )
    st.dataframe(pd.DataFrame(table_rows), hide_index=True, use_container_width=True)

    # 6-month histogram (or first available horizon)
    fwd = result.get("forward_returns") or {}
    plot_horizon = (
        6 if 6 in fwd and fwd[6] else (sorted(fwd.keys())[0] if fwd else None)
    )
    if plot_horizon and fwd[plot_horizon]:
        values_pct = [v * 100 for v in fwd[plot_horizon]]
        fig = go.Figure(data=[go.Histogram(x=values_pct, nbinsx=20)])
        fig.update_layout(
            title=f"Forward {plot_horizon}-month returns on {ticker} after this observation",
            xaxis_title="Forward return (%)",
            yaxis_title="Count",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False,
        )
        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption(
            "Histogram unavailable — instances are too recent to have full forward returns."
        )

    if result["summary"].get(6, {}).get("median") is not None:
        median_6m = result["summary"][6]["median"]
        if median_6m < 0:
            st.markdown(
                f":warning: **Heads up:** historically on {ticker}, this "
                f"observation has been followed by a *negative* median 6-month "
                f"return ({format_pct(median_6m)}). This signal has not earned "
                f"trust on this ticker."
            )
        elif median_6m < 0.01:
            st.markdown(
                f":information_source: Historically on {ticker}, this observation "
                f"has been followed by roughly flat 6-month returns "
                f"({format_pct(median_6m)} median). The signal hasn't been meaningful."
            )


def _render_observation_card(
    obs: observations.Observation,
    prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame | None,
    config: Config,
) -> None:
    """Render one observation: framing text + honesty layer."""
    with st.container(border=True):
        st.markdown(f"#### {obs.headline}")
        st.markdown(f"**What happened:** {obs.what_happened}")
        with st.expander("What different camps read into this", expanded=True):
            st.markdown(obs.what_camps_read_into_it)
        with st.expander("Friction questions to consider", expanded=True):
            st.markdown(obs.what_to_consider)
        _render_honesty_panel(obs.ticker, obs.type, prices, benchmark_prices, config)


def _checklist_dialog(
    ticker: str,
    exchange: str,
    active_observations: list[observations.Observation],
    latest_price: float | None,
) -> None:
    """Modal: render the 6-item checklist + note + action, save to journal."""
    st.markdown("### Research checklist")
    st.caption(
        "Tick what you've actually done. Be honest with yourself — this entry "
        "is what you'll re-read in 6 months."
    )
    checklist_state: dict[str, bool] = {}
    for i, item in enumerate(cl.CHECKLIST_ITEMS):
        checked = st.checkbox(item, key=f"chk_{ticker}_{i}")
        checklist_state[item] = checked

    note = st.text_area(
        "One-sentence decision note (required)",
        key=f"note_{ticker}",
        placeholder="e.g. 'Considering trimming RY because the bank sector "
        "drawdown observation matches my macro read.'",
    )
    action = st.radio(
        "Action you're planning",
        cl.ACTIONS,
        key=f"action_{ticker}",
        horizontal=True,
    )
    cols = st.columns([1, 1, 4])
    with cols[0]:
        submit = st.button("Save to journal", type="primary", key=f"save_{ticker}")
    with cols[1]:
        cancel = st.button("Cancel", key=f"cancel_{ticker}")

    if cancel:
        st.session_state.show_checklist = False
        st.rerun()

    if submit:
        if not note.strip():
            st.error("Decision note is required.")
            return
        # Serialize observations to JSON-friendly dicts.
        obs_payload = [
            {
                **{k: v for k, v in asdict(obs).items() if k != "detected_at"},
                "detected_at": obs.detected_at.isoformat(),
            }
            for obs in active_observations
        ]
        try:
            cl.save_journal_entry(
                ticker=ticker,
                exchange=exchange,
                active_observations=obs_payload,
                checklist_state=checklist_state,
                decision_note=note,
                action_planned=action,
                price_at_decision=latest_price,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not save: {exc}")
            return
        st.session_state.show_checklist = False
        st.success(
            "Saved. Your decision is logged. Now go act (or don't) — and "
            "review this entry later."
        )


def render(config: Config) -> None:
    """Streamlit entry point for the Ticker Review page."""
    st.title("Review a ticker")
    st.caption(DISCLAIMER_SHORT)

    cols = st.columns([3, 2, 1])
    with cols[0]:
        ticker_input = st.text_input(
            "Ticker",
            value=st.session_state.get("review_ticker", ""),
            key="review_ticker_input",
            placeholder="e.g. AAPL, RY, SHOP",
        )
    with cols[1]:
        exchange = st.selectbox(
            "Exchange",
            EXCHANGES,
            index=EXCHANGES.index(st.session_state.get("review_exchange", "NYSE")),
            key="review_exchange_input",
        )
    with cols[2]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        go_clicked = st.button("Review", type="primary", use_container_width=True)

    if go_clicked:
        st.session_state.review_ticker = ticker_input.strip().upper()
        st.session_state.review_exchange = exchange
        st.session_state.show_checklist = False
        _cached_fetch.clear()

    ticker = st.session_state.get("review_ticker", "").strip().upper()
    if not ticker:
        st.info("Enter a ticker and click Review to begin.")
        return

    try:
        symbol = normalize_ticker(ticker, exchange)
    except ValueError as exc:
        st.error(str(exc))
        return

    _staleness_banner(symbol)

    with st.spinner(f"Fetching price history for {symbol}…"):
        prices = _cached_fetch(symbol)
        info = _cached_info(symbol)

    if prices.empty:
        st.error(
            f"No price data available for {symbol}. Check the ticker symbol and "
            "exchange, or try again later if the network is down."
        )
        return

    # Header
    long_name = info.get("long_name", display_ticker(ticker, exchange))
    latest_price = float(prices["adj_close"].iloc[-1])
    last_date = prices.index[-1].strftime("%Y-%m-%d")
    st.markdown(
        f"### {long_name}  \n"
        f"`{symbol}` · last close **{latest_price:.2f}** on {last_date} · "
        f"{len(prices):,} trading days of history"
    )
    if info.get("sector"):
        st.caption(
            f"Sector: {info['sector']}  ·  Industry: {info.get('industry', '—')}"
        )

    # Benchmark for correlation_decoupling
    benchmark_symbol = config.benchmarks.default
    benchmark_prices = _cached_fetch(benchmark_symbol)
    if benchmark_prices.empty:
        benchmark_prices = None

    active = observations.get_active_observations(
        ticker=ticker, prices=prices, benchmark_prices=benchmark_prices
    )

    if not active:
        st.success(
            "**No active observations on this ticker right now.** "
            "That itself is information — none of the eight detectors are "
            "currently flagging anything worth a second look."
        )
    else:
        st.markdown(
            f"## {len(active)} active observation{'s' if len(active) > 1 else ''}"
        )
        for obs in active:
            _render_observation_card(obs, prices, benchmark_prices, config)

    st.markdown("---")

    if st.button("I'm considering acting on this", type="primary"):
        st.session_state.show_checklist = True

    if st.session_state.get("show_checklist"):
        with st.container(border=True):
            _checklist_dialog(ticker, exchange, active, latest_price)
