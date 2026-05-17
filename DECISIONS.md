# DECISIONS.md — Architectural Decision Log

> **For Claude Code:** Before making an architectural choice not in SPEC.md or PROGRESS.md, check here.
> If decided already, follow it — do not re-litigate.
> If new fork: add to "Pending Decisions" and flag to user.

---

## Settled Decisions

### DEC-000: Pivot to "Option A — Anti-Signal Tool" framing
**Date:** 2026-05-08
**Decision:** Reduce v1 scope by ~70% to focus on three differentiators: the Observations engine, the per-ticker historical honesty layer, and the Research Checklist with decision journal.
**Rationale:** A landscape review showed the v0.2 spec largely duplicated free or cheap existing tools (Empower, Yahoo Finance, Sharesight, Finviz, Stock Rover). Building those features would mean spending significant time creating worse versions of products already available. The genuinely novel pieces — observations with the meta-conversation included, per-ticker historical context, and the friction layer — are not available anywhere and directly serve the user's stated philosophy of disciplined long-term investing.
**Trade-off accepted:** No charting, no dashboard, no auto-refresh, no portfolio tracking, no sector heatmaps, no multi-asset comparison. Users keep using existing tools for those jobs.
**Implications:** Spec is now four phases, not six. Single-Asset Deep Dive view is gone. Comparison view is gone. Sector view is gone. Auto-refresh is gone. The tool is opened on demand when the user is making a decision, not run as a background dashboard.

---

### DEC-001: No buy/sell signals — observations only
**Date:** 2026-05-07
**Decision:** No buy/sell/hold recommendations anywhere. All pattern output uses the three-part observation format: (1) what's happening, (2) what camps read into it, (3) what to consider before acting.
**Rationale:** User wants to make their own decisions informed by data, not be told what to do. Observations introduce useful friction and are honest about the limits of technical analysis.
**Implications:** UI elements, function names, and display text must avoid directional trade language.

---

### DEC-002: yfinance as sole data source (v1)
**Date:** 2026-05-07
**Decision:** All market data from `yfinance`. No fallback in v1.
**Rationale:** Free, no API key, covers US + TSX + ETFs + indices. End-of-day staleness is fine — this tool isn't for intraday decisions anyway.
**Upgrade path:** If yfinance breaks: Alpha Vantage (free, slow) → Polygon.io (paid, reliable). Changes confined to `src/data_fetch.py` if abstraction is clean.
**Implications:** All yfinance calls go through `src/data_fetch.py`. Nowhere else imports yfinance.

---

### DEC-003: Streamlit as UI framework
**Date:** 2026-05-07
**Decision:** Use Streamlit.
**Rationale:** Minimal frontend code. User opens the app on demand, completes a flow, closes it. Streamlit's request-response model is fine for this — we're not building a real-time dashboard (and explicitly don't want to).

---

### DEC-004: SQLite for all storage
**Date:** 2026-05-07
**Decision:** SQLite via stdlib `sqlite3`. No ORM.
**Rationale:** Lightweight, zero-dep, easy to inspect/export. Data volumes here are tiny.
**Implications:** Schemas in respective Python modules. Parameterized queries always — no f-string SQL.

---

### DEC-005: TSX ticker normalization
**Date:** 2026-05-07
**Decision:** TSX tickers stored bare (e.g. `RY`) with `exchange = "TSX"`. `.TO` suffix added by `utils.normalize_ticker()` at fetch time.
**Edge case:** Ambiguous tickers (e.g. `SHOP` on both NYSE and TSX) require explicit `exchange` value or `normalize_ticker()` raises a clear error.

---

### DEC-006: Adjusted close for all returns
**Date:** 2026-05-07
**Decision:** All return calculations use adjusted close. Never raw close.
**Rationale:** Accounts for splits and dividends. Critical for honesty layer accuracy — incorrect forward returns would defeat the entire point.
**Implications:** `adj_close` always present in `data_fetch.fetch_price_history()` output. Honesty layer math uses this column exclusively.

---

### DEC-007: Config in config.toml
**Date:** 2026-05-07
**Decision:** All user-configurable values in `config.toml`, loaded once at startup.
**Values:** user profile (age, horizon, risk tolerance, goals), thresholds (drawdown %, vol lookback period), benchmark ticker.
**Rationale:** Customization without touching code.

---

### DEC-008: Observation framing text is hand-written and stable
**Date:** 2026-05-08
**Decision:** All `what_camps_read_into_it` and `what_to_consider` text lives in `src/observation_templates.py`, hand-written per observation type. Not generated, not interpolated beyond `{ticker}` substitution.
**Rationale:** The framing is the product. Generated framing would drift, vary, and risk introducing buy/sell language. Hand-writing it once means we can revise it deliberately and version-control its evolution.
**Implications:** Adding a new observation type requires writing new template text. There's no way around this — and that's fine, because the friction of having to write thoughtful framing is itself a check on adding observations recklessly.

---

### DEC-009: Honesty layer must show unflattering results unfiltered
**Date:** 2026-05-08
**Decision:** When the honesty layer surfaces historical forward-return data, it shows the raw distribution, even if a popular signal looks unhelpful or harmful on a given ticker.
**Rationale:** The entire point of the honesty layer is to undermine signals that don't deserve the user's trust on the asset in question. Filtering or weighting results to make signals look more useful would defeat the tool's purpose and turn it into the kind of confirmation-bias-affirming product the user is explicitly trying to avoid.
**Implications:** No "smoothing" of histogram outliers. No selecting only "successful" instances. No omitting the median if it's negative. The numbers are the numbers.

---

### DEC-010: No share counts or cost basis tracking
**Date:** 2026-05-08
**Decision:** Holdings table stores ticker + exchange only. No share counts, cost basis, or purchase dates.
**Rationale:** Sharesight and Empower do this exhaustively and well. Duplicating that work pulls scope back toward v0.2 territory.
**Implications:** Portfolio Check page (Phase 4) uses equal-weight assumption with a clear caveat — see PEND-002.

---

### DEC-011: Honesty layer sample-size handling — tiered transparency
**Date:** 2026-05-17
**Decision:** Always show forward-return summary stats; tag each result with a confidence tier based on N:
- `very_low`: N < 5
- `low`: 5 ≤ N < 15
- `moderate`: 15 ≤ N < 30
- `good`: N ≥ 30
**Rationale:** Hiding data is paternalistic and contradicts the honesty-layer mission. Tiered tags let the user judge for themselves what to do with N=3.
**Implications:** `summarize_outcomes()` returns a `sample_tier` field. UI renders the tier visibly next to the number of instances. Resolves PEND-001.

---

### DEC-012: Portfolio Check — optional share counts
**Date:** 2026-05-17
**Decision:** Holdings may include an optional `shares` column. Portfolio Check uses real dollar weights when shares are present; falls back to equal-weight (with a banner) when they are not.
**Rationale:** User opted to allow more accurate concentration checks. Cost basis and purchase dates are still excluded — Sharesight/Empower own that.
**Implications:** Partially supersedes DEC-010. `holdings` schema adds `shares REAL NULL`. `advice.py` computes weights from `shares * latest_price` per ticker. Banner switches based on whether all holdings have shares. Resolves PEND-002.

---

### DEC-013: Drop pandas-ta — use pandas directly
**Date:** 2026-05-17
**Decision:** Do not include `pandas-ta` in requirements. Implement MA, rolling volatility, rolling max/min, and correlation directly with pandas in `src/indicators.py`.
**Rationale:** Python 3.14 removes `pkg_resources` (which pandas-ta still imports at module load); installs and runtime imports are unreliable. The handful of indicators we need are one-line pandas calls — the dependency adds risk without saving meaningful code.
**Implications:** Approved-libraries list in CLAUDE.md should drop `pandas-ta`. `requirements.txt` does not include it. If a future observation type needs a less trivial indicator, revisit.

---

## Pending Decisions

### PEND-003: TSX historical data depth verification
**Status:** Unresolved — must verify in Phase 1
**Question:** Does yfinance return enough history on TSX tickers (RY.TO, SHOP.TO, ENB.TO) to make the honesty layer useful? US tickers typically have decades; TSX may have less.
**Action needed:** Run `yfinance.Ticker("RY.TO").history(period="max")` in Phase 1 and document available date ranges. If insufficient, decide whether to lower historical-instance expectations or note the limitation in the UI.
**Decision needed from:** Claude Code during Phase 1.10 review

---

## Decision Log Format (for future entries)

```
### DEC-XXX: Short title
**Date:** YYYY-MM-DD
**Decision:** What was decided, in one sentence.
**Rationale:** Why.
**Trade-off accepted:** What was given up.
**Implications:** What this means for the codebase.
```
