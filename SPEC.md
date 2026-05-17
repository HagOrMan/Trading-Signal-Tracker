# Anti-Signal Tool — Spec Document

**Version:** 0.3 (Option A pivot)
**Last updated:** 2026-05-08
**Status:** Pre-implementation

> **For Claude Code:** This file is the source of truth for what the app is and why decisions were made.
> Read this to understand intent. Read PROGRESS.md for what to build next. Log forks in DECISIONS.md.

**Changelog from v0.2:**
- Pivoted to "Option A — Anti-Signal Tool" framing after discovering the v0.2 spec duplicated existing free tools (Empower, Yahoo Finance, Sharesight, Stock Rover, Snowball)
- Removed: Single-Asset Deep Dive as primary view, Multi-Asset Comparison, Sector heatmap, generic alerts, auto-refresh loop
- Promoted to core: Observations engine (was §6.5), per-ticker historical backtest of observations (was Phase 7), Research Checklist (was §5.6C)
- Reduced scope by ~70%; v1 is a focused, opinionated tool with a single point of view

---

## 1. Purpose

A small, opinionated tool that does one thing: when you're about to make an investment decision, it slows you down, shows you the relevant observations on the asset, shows how those observations have *historically played out on that specific asset*, and walks you through a research checklist before you act.

It is not a portfolio dashboard. It is not a charting tool. It is a **decision speed bump** with a built-in honesty layer.

---

## 2. The Core Insight

Existing free tools (Yahoo Finance, Empower, Sharesight, Finviz, Stock Rover) cover charting, allocation analysis, sector heatmaps, and generic alerts well. What none of them do:

1. Frame patterns as **observations with the meta-conversation included** — what's happening, what different camps read into it, what to consider before acting
2. Show **how reliable each observation type has been on YOUR specific ticker** historically — not generic backtests, your tickers
3. Force **explicit friction** between observation and action via a research checklist

Those three things, together, target the actual failure mode of retail investing: acting on signals that *feel* meaningful in the moment without checking whether they've ever meant anything for the asset in question.

---

## 3. What This Tool Is Not

This tool does not replace, and is not trying to compete with:

- **Yahoo Finance / brokerage charting** for daily price/volume/MA viewing
- **Empower / Sharesight** for portfolio tracking, allocation breakdown, multi-currency totals
- **Finviz / Stock Rover** for sector heatmaps and screening
- **Snowball Analytics** for dividend tracking and rebalancing tools

The user is expected to use those tools for their stated jobs. This tool is for the moment *before pulling the trigger*.

It is also not financial advice, not a forecasting tool, and not a buy/sell signal generator. See §10.

---

## 4. User Profile

- Amateur investor, Burlington ON, US (NYSE/NASDAQ) and Canadian (TSX) markets
- Comfortable with Python
- Long-term investor (40+ year horizon), believes in diversification and discipline
- Already uses other tools for portfolio tracking and charting
- Wants a **personal accountability tool** to challenge his own decisions before he acts

---

## 5. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | User proficient |
| Data | `yfinance` | Free, covers US + TSX, sufficient for end-of-day analysis |
| Data manipulation | `pandas` | Standard |
| Indicators | `pandas-ta` | MAs, volatility |
| UI | `streamlit` | Single-page web UI, minimal frontend code |
| Charts | `plotly` | Only for contextualizing observations — not the focus |
| Storage | SQLite | Holdings, watchlist, observation history, backtest cache |
| Config | `config.toml` | User profile, thresholds |

---

## 6. Core Features

### 6.1 Holdings & Watchlist

Minimal — these exist only so the tool knows which tickers to evaluate.

- Add tickers (with exchange) via a simple table editor
- No share counts, no cost basis, no purchase dates required (Sharesight/Empower do that better)
- Optional: paste a list of tickers; the tool figures out the exchange where unambiguous
- Persisted to `portfolio.db`

### 6.2 The Observations Engine

When you load a ticker, the tool runs every observation detector against its current price history and surfaces only the patterns that are *currently active*.

Each observation is structured as:

```
{
  ticker, type, headline,
  what_happened: "<factual statement>",
  what_camps_read_into_it: "<the disagreement, neutrally stated>",
  what_to_consider: "<friction questions specific to this pattern>",
  detected_at: <date>,
  observation_id: <stable hash>
}
```

**Observation types in v1:**

| Type | Triggers when |
|---|---|
| `ma_crossover_bullish` | 50-day MA crosses above 200-day MA in last 30 days |
| `ma_crossover_bearish` | 50-day MA crosses below 200-day MA in last 30 days |
| `new_52w_high` | Closed above prior 52w high in last 5 trading days |
| `new_52w_low` | Closed below prior 52w low in last 5 trading days |
| `vol_regime_elevated` | 30-day volatility in top 10th percentile of 2-year history |
| `vol_regime_compressed` | 30-day volatility in bottom 10th percentile of 2-year history |
| `drawdown_significant` | Currently >15% below recent (1y) high |
| `correlation_decoupling` | 60-day correlation with benchmark dropped >0.3 from 1y average |

For each observation, the `what_camps_read_into_it` and `what_to_consider` fields are written *once*, by hand, in `src/observation_templates.py` — these are not generated dynamically. The whole point is that the framing is thoughtful and stable.

### 6.3 The Honesty Layer (the differentiator)

For any observation currently active on a ticker, show: **historically, when this observation type fired on this specific ticker, what happened next?**

For each (ticker, observation_type) pair:
- Find every historical instance of this observation in the ticker's price history (going back as far as available)
- For each instance, measure forward returns over 1 / 3 / 6 / 12 month horizons
- Display as a small results panel:
  - Number of historical occurrences
  - Distribution of forward returns (median, 25th/75th percentile, win rate)
  - A small histogram or strip plot of outcomes
  - Honest framing: "This observation has fired N times on TICKER. Forward 6-month median return: X%. The 25-75 range was [A%, B%]. This is one ticker's history; it's not predictive."

**Critical UI principle:** the honesty layer should sometimes show observations that *don't work*. If "golden cross on AAPL" historically preceded slightly negative returns, the app must show that clearly — even if it makes the observation feel useless. That's the entire point.

Cached in `backtest.db` keyed on `(ticker, observation_type, ticker_data_hash)` so it doesn't recompute on every load.

### 6.4 The Research Checklist

When the user has reviewed observations and the honesty layer, before they leave to go execute a trade, they click an "I'm considering acting on this" button which opens a modal:

- [ ] Have I checked recent news/earnings/filings for this company? (link out to a news search)
- [ ] Have I confirmed *why* this pattern is appearing — fundamentals or sentiment?
- [ ] Does this fit my long-term plan, or am I reacting to short-term noise?
- [ ] If I act on this, what specifically would change my mind later (exit plan)?
- [ ] Am I within my normal rebalancing schedule, or making an unscheduled trade?
- [ ] Have I looked at the honesty layer above? Does the historical record support my read?

Below the checklist: a free-text "decision journal" field. The user writes one sentence about what they're about to do and why. Saved to `decisions.db` with the ticker, the active observations, and the user's note. This becomes the basis for self-review later — "six months ago I said X about MSFT — was I right?"

This is the entire reason the tool exists.

### 6.5 Personalized Portfolio Check

A single page — not a primary feature, but a useful sanity check the user runs occasionally. Reads holdings + user profile from config, reports:

- Sector concentration vs 25% rule of thumb
- Geographic split vs global market cap (~60% US / 3% CA / 37% intl)
- Single-name concentration (>10% flag)
- Equity-only assumption noted (this tool doesn't track bonds/cash — Sharesight/Empower do)

Each item: rule of thumb → user's value → what to consider. Same observation framing.

**Explicit limitation in the UI:** "For full portfolio tracking with multi-currency, dividends, and tax reporting, use Sharesight or Empower. This page is a quick sanity check, not a tracking tool."

---

## 7. The User Flow

The tool is designed around one workflow:

1. User is thinking about buying or selling something
2. Opens the tool, types in the ticker (or selects from holdings/watchlist)
3. Sees: active observations + honesty layer for each
4. Clicks "I'm considering acting on this" → research checklist + decision journal
5. Closes the tool, goes to their brokerage to act (or doesn't)

Secondary workflow: occasionally open the Portfolio Check page for a sanity scan.

There is no dashboard. There is no auto-refresh. There is no "watch the market all day" mode.

---

## 8. Data & Caching

- Price data fetched on demand per ticker, cached in `cache.db` keyed on `(ticker, date)`
- Cache valid for the trading day; expires overnight
- Backtest results cached in `backtest.db`, invalidated when underlying price data extends
- On network failure: show cached data with a stale-data warning
- All return calculations use adjusted close

**Limitations shown in app footer:**
- yfinance is an unofficial Yahoo Finance scraper — can break
- End-of-day analysis only — not for intraday decisions
- Honesty layer reflects historical patterns of the specific ticker; past performance does not predict future results

---

## 9. Project Structure

```
anti_signal_tool/
├── app.py                          # Streamlit entry, page routing
├── config.toml                     # User profile, thresholds
├── requirements.txt
├── CLAUDE.md
├── SPEC.md
├── PROGRESS.md
├── DECISIONS.md
├── data/
│   ├── cache.db                    # Price history cache
│   ├── portfolio.db                # Holdings + watchlist
│   ├── backtest.db                 # Cached observation backtests
│   └── decisions.db                # Decision journal entries
├── src/
│   ├── data_fetch.py               # yfinance wrapper, cache layer
│   ├── indicators.py               # MA, vol, drawdown, correlation
│   ├── observations.py             # Detector functions for each observation type
│   ├── observation_templates.py    # Hand-written framing text per observation type
│   ├── honesty_layer.py            # Historical backtest of observations on a ticker
│   ├── checklist.py                # Research checklist + decision journal logic
│   ├── advice.py                   # Personalized portfolio check
│   ├── portfolio.py                # Holdings/watchlist CRUD
│   ├── utils.py                    # Ticker normalization, formatting
│   └── views/
│       ├── ticker_review.py        # Main view: observations + honesty layer + checklist
│       ├── portfolio_check.py      # Sanity check page
│       └── journal.py              # Past decisions review
└── tests/
```

---

## 10. Disclaimers (must appear in UI)

- This tool is for personal informational use only and does not constitute financial advice.
- Observations are data patterns worth researching — not buy/sell recommendations.
- The honesty layer shows historical patterns on a single ticker; past performance does not predict future results.
- Market data is end-of-day and may be delayed or occasionally inaccurate.
- For full portfolio tracking, charting, and tax reporting, use purpose-built tools (Sharesight, Empower, Yahoo Finance).

---

## 11. Build Phases

| Phase | Name | Deliverables |
|---|---|---|
| 1 | Foundation | Scaffold, SQLite, data fetch + cache, ticker review view with one observation type wired through |
| 2 | Observations + Honesty | All 8 observation detectors + honesty layer backtesting for each |
| 3 | Checklist + Journal | Research checklist modal, decision journal storage, journal review page |
| 4 | Portfolio Check + Polish | Personalized portfolio check page, error states, disclaimers, empty states |

That's it. Four phases. No Phase 5/6 in v1.

**Out of scope** (and why):
- Auto-refresh and live alerts → not a dashboard tool
- News integration → use Yahoo Finance / brokerage apps
- Multi-asset comparison charts → Yahoo Finance does this for free
- Sector heatmap → Finviz does this beautifully and free
- Performance logging → Sharesight does this exhaustively
- Multi-currency totals → Sharesight does this
- Cost basis tracking → Sharesight does this
- News/sentiment ML → out of scope; was speculative even in v0.2

---

## 12. Open Questions

- **Honesty layer minimum sample size:** if a ticker only has 3 historical instances of an observation, is the result useful? Suggest showing the data with a "low sample" warning rather than hiding it. Decide before Phase 2.
- **Decision journal review cadence:** how should the journal page surface old decisions for review? Email reminders are out (no notifications). Maybe a "decisions older than 6 months" tab. Decide in Phase 3.
- **TSX historical data depth:** yfinance coverage of TSX historical data may be thinner than US — verify in Phase 1 with a few real TSX tickers (RY.TO, SHOP.TO, ENB.TO).

---

## 13. What Honest Success Looks Like

In 6 months, the user has:
- A decision journal with ~10–30 entries
- Reviewed at least some entries against actual outcomes
- Caught themselves *not* making a trade because the checklist or honesty layer surfaced something they'd missed
- Continued using Yahoo Finance / Empower / Sharesight for everything else

That's a successful tool. Not "I built a Bloomberg terminal." A working accountability mechanism for one specific failure mode.
