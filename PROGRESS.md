# PROGRESS.md — Build Tracker

> **For Claude Code:** Start here every session. Find current phase. Find first unchecked task. Read relevant source files. Build it. Check it off.
> If task is ambiguous, check SPEC.md for intent first.
> Architectural forks not covered here or in DECISIONS.md → add to DECISIONS.md "Pending" and flag.

**Current phase: 1 — Foundation**

---

## Phase 1 — Foundation
*Goal: One ticker can be reviewed end-to-end with one observation type wired through. Proves the whole vertical works.*

### 1.1 Project scaffold
- [ ] Create `requirements.txt` with pinned versions: `streamlit`, `yfinance`, `pandas`, `pandas-ta`, `plotly`, `tomli` (for Python <3.11), `pytest`
- [ ] Create `config.toml` with: `[user_profile]` (age_range, horizon_years, risk_tolerance), `[thresholds]` (drawdown_pct, vol_lookback_years), `[benchmarks]` (default = "SPY")
- [ ] Create `data/` directory with `.gitkeep`; add `data/*.db` to `.gitignore`
- [ ] Create `src/__init__.py`, `src/views/__init__.py`, `tests/__init__.py`
- [ ] Verify `streamlit hello` runs (confirms environment)

### 1.2 SQLite schemas
- [ ] In `src/portfolio.py`: `init_db()` creates `portfolio.db`:
  - `holdings (id, ticker, exchange, added_at TEXT)`
  - `watchlist (id, ticker, exchange, added_at TEXT)`
  - Note: no shares/cost_basis/purchase_date — this isn't a tracking tool
- [ ] CRUD functions: `add_holding()`, `remove_holding()`, `get_holdings()`, watchlist equivalents — parameterized queries only
- [ ] In `src/data_fetch.py`: `init_cache_db()` creates `cache.db`:
  - `prices (ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume INTEGER, PRIMARY KEY (ticker, date))`
- [ ] Tests: `tests/test_portfolio.py` — CRUD round-trip with in-memory SQLite

### 1.3 Ticker utilities
- [ ] In `src/utils.py`:
  - `normalize_ticker(ticker: str, exchange: str) -> str` — TSX → `.TO` suffix; US → unchanged
  - `format_pct(value: float, decimals: int = 2) -> str`
  - `format_currency(value: float, currency: str = "USD") -> str` (currency-agnostic since this isn't a tracking tool)
- [ ] Tests: `tests/test_utils.py`

### 1.4 Data fetch layer
- [ ] In `src/data_fetch.py`:
  - `fetch_price_history(ticker: str, period: str = "max") -> pd.DataFrame` — cache-first, fetches missing range from yfinance, returns adjusted close in `adj_close` column
  - `fetch_ticker_info(ticker: str) -> dict` — basic stats; return empty dict on failure
  - `get_cache_age(ticker: str) -> int | None` — for staleness banner
- [ ] Tests: `tests/test_data_fetch.py` — mock yfinance, verify cache hit/miss

### 1.5 Indicators (minimum needed for observations)
- [ ] In `src/indicators.py` (all pure functions):
  - `moving_average(prices: pd.Series, window: int) -> pd.Series`
  - `rolling_volatility(prices: pd.Series, window: int = 30) -> pd.Series` — annualized std of log returns
  - `rolling_max(prices: pd.Series, window: int) -> pd.Series` — for 52w high
  - `rolling_min(prices: pd.Series, window: int) -> pd.Series` — for 52w low
- [ ] Tests with known synthetic series

### 1.6 First observation: `ma_crossover_bullish`
- [ ] In `src/observation_templates.py`: define `OBSERVATION_TEMPLATES` dict keyed on observation type. For `ma_crossover_bullish`:
  - `headline`: "Bullish MA crossover (golden cross) on {ticker}"
  - `what_camps_read_into_it`: hand-written paragraph covering the trend-follower view ("momentum confirmation"), the contrarian view ("often a lagging indicator that fires after most of the move"), and an academic note (mention Hurst & related research showing mixed evidence)
  - `what_to_consider`: 4–5 friction questions specific to MA crossovers — especially "is this a confirmation of news you already considered, or new information?"
- [ ] In `src/observations.py`:
  - `Observation` dataclass: `{ticker, type, headline, what_happened, what_camps_read_into_it, what_to_consider, detected_at}`
  - `detect_ma_crossover_bullish(ticker: str, prices: pd.DataFrame) -> Observation | None` — fires if 50d MA crossed above 200d MA in the last 30 trading days
  - `get_active_observations(ticker: str, prices: pd.DataFrame) -> list[Observation]` — calls all detectors, returns active ones (Phase 1: just this one)
- [ ] Tests: synthetic price series with engineered crossover

### 1.7 Honesty layer — first wiring
- [ ] In `src/honesty_layer.py`:
  - `find_historical_instances(prices: pd.DataFrame, observation_type: str) -> list[date]` — scans full history, returns all dates this observation would have fired
  - `forward_returns(prices: pd.DataFrame, instance_dates: list[date], horizons_months: list[int] = [1, 3, 6, 12]) -> dict` — for each horizon, returns list of forward returns
  - `summarize_outcomes(forward_returns: dict) -> dict` — for each horizon: count, median, p25, p75, win_rate
  - Cache results in `backtest.db` keyed on `(ticker, observation_type, last_data_date)`
- [ ] Tests: synthetic ticker with engineered instances → verify summary stats are correct
- [ ] Tests: low-sample-size case (< 5 instances) returns a `low_sample: True` flag

### 1.8 Ticker review view (the main view)
- [ ] `src/views/ticker_review.py`: write `render()`
  - Ticker input (text + exchange selector)
  - Calls `normalize_ticker()`, `fetch_price_history(period="max")`, `get_active_observations()`
  - For each active observation: render an observation card showing `headline`, `what_happened`, `what_camps_read_into_it`, `what_to_consider`
  - Below each card: render honesty layer panel — call `find_historical_instances()` + `forward_returns()` + `summarize_outcomes()`, display table of stats per horizon, render simple Plotly histogram of forward 6-month returns
  - If `low_sample: True`: show "Only N historical instances — limited statistical confidence" banner
  - If no active observations: show "No active observations on this ticker right now. That itself is information." (this framing matters)
  - Stale data banner if cache age > 1 trading day

### 1.9 App entry
- [ ] In `app.py`:
  - Load `config.toml`
  - Call all `init_db()` functions on startup
  - Sidebar: app title, brief description, disclaimer footer (full text from CLAUDE.md)
  - Main area: just the ticker review view in Phase 1
- [ ] Confirm: `streamlit run app.py` works; `AAPL` with engineered or real recent crossover renders observation + honesty layer

### 1.10 Phase 1 review checkpoint
- [ ] All tests pass
- [ ] App runs end-to-end for both a US ticker and a TSX ticker
- [ ] Honesty layer shows at least one *unflattering* historical case (find a ticker where MA crossover historically didn't help — confirms we're not filtering)
- [ ] Disclaimer visible

---

## Phase 2 — Observations + Honesty (full set)
*Goal: All 8 observation types working, with honesty layer for each.*

### 2.1 Remaining observation detectors
- [ ] `detect_ma_crossover_bearish` (death cross — 50d crosses below 200d in last 30 days)
- [ ] `detect_new_52w_high` (closed above prior 52w high in last 5 days)
- [ ] `detect_new_52w_low` (closed below prior 52w low in last 5 days)
- [ ] `detect_vol_regime_elevated` (30-day vol in top 10th pct of 2y history)
- [ ] `detect_vol_regime_compressed` (30-day vol in bottom 10th pct of 2y history)
- [ ] `detect_drawdown_significant` (currently >15% below recent 1y high)
- [ ] `detect_correlation_decoupling` (60-day corr with benchmark dropped >0.3 from 1y average — needs benchmark price series)
- [ ] Tests for each: synthetic series engineered to trigger / not trigger

### 2.2 Templates for each observation type
- [ ] In `src/observation_templates.py`: hand-write `headline`, `what_camps_read_into_it`, `what_to_consider` for each of the 7 new types
- [ ] Each `what_camps_read_into_it` should cite the actual disagreement neutrally — e.g. for `new_52w_low`: "Momentum traders often treat new lows as a sell signal. Value investors often treat them as a potential buying opportunity if fundamentals are unchanged. The disagreement persists because new lows alone, without context, don't determine which interpretation wins."
- [ ] Each `what_to_consider` is 4–5 questions specific to that pattern

### 2.3 Honesty layer for each observation type
- [ ] Extend `find_historical_instances()` to handle all 8 observation types
- [ ] Verify backtest cache invalidation works correctly when underlying price data extends
- [ ] Tests: each observation type has at least one synthetic ticker test where forward returns are known

### 2.4 Sample size handling
- [ ] If <5 instances: show clear "low sample" warning; still display the data but de-emphasize visually
- [ ] If 0 instances: explain that this observation has never fired on this ticker historically — that's a meaningful piece of context
- [ ] Decide and document in DECISIONS.md (PEND-001) the exact threshold

### 2.5 Phase 2 review checkpoint
- [ ] All 8 detectors tested and working
- [ ] All templates written and read naturally — no robotic placeholders
- [ ] Honesty layer renders for all 8 types
- [ ] At least one ticker shows multiple active observations simultaneously (e.g. drawdown + new 52w low)

---

## Phase 3 — Checklist + Journal
*Goal: The friction layer. The actual reason this tool exists.*

### 3.1 Decision journal schema
- [ ] In `src/checklist.py`: `init_decisions_db()` creates `decisions.db`:
  - `journal (id, date TEXT, ticker, exchange, active_observations_json TEXT, checklist_state_json TEXT, decision_note TEXT, action_planned TEXT)`
  - `action_planned` enum: "buy" | "sell" | "hold" | "research_more" | "do_nothing"
- [ ] CRUD functions: `save_journal_entry()`, `get_all_entries()`, `get_entries_for_ticker(ticker)`, `get_entries_older_than(months)`

### 3.2 Research checklist component
- [ ] In `src/checklist.py`: define `CHECKLIST_ITEMS` constant — list of 6 items from SPEC.md §6.4
- [ ] In `src/views/ticker_review.py`: add "I'm considering acting on this" button below the observations
- [ ] Clicking opens a Streamlit dialog/expander modal:
  - Renders all 6 checklist items as `st.checkbox`
  - Free-text "Decision note" field (`st.text_area`) — required to submit
  - Action selector (`st.radio`): buy / sell / hold / research_more / do_nothing
  - "Save to journal" button — writes to `decisions.db` with all checklist state, observations, note, action
- [ ] Submit triggers a confirmation: "Saved. Your decision is logged. Now go act (or don't) — and review this entry later."

### 3.3 Journal review page
- [ ] `src/views/journal.py`: write `render()`
  - Default tab: "Recent" (last 30 days)
  - Tab: "Old enough to review" (entries >6 months old) — surfaces past decisions for retrospection
  - Each entry displays: date, ticker, observations active at the time, action planned, note, current price + return since the journaled date
  - Sortable by date, ticker, or "biggest miss" (largest delta between expected outcome and actual)

### 3.4 Wire up navigation
- [ ] In `app.py`: sidebar nav now has: "Review a Ticker" | "Journal"
- [ ] Phase 4 will add the Portfolio Check page

### 3.5 Phase 3 review checkpoint
- [ ] Tests pass
- [ ] User can complete the full flow: review ticker → see observations + honesty layer → click button → fill checklist → save → reopen journal → see entry
- [ ] Journal "old enough to review" tab works (mock by inserting a test entry with backdated timestamp)

---

## Phase 4 — Portfolio Check + Polish
*Goal: Optional sanity-check page + production-quality UX.*

### 4.1 Personalized portfolio check
- [ ] In `src/advice.py`:
  - `PortfolioObservation` dataclass: `{check_name, rule_of_thumb, user_value, benchmark_value, what_to_consider, severity}`
  - `check_sector_concentration(holdings, prices_dict) -> PortfolioObservation`
  - `check_geographic_split(holdings) -> PortfolioObservation` (use simple US/CA/intl heuristic from exchange + sector)
  - `check_single_name_concentration(holdings, prices_dict) -> PortfolioObservation` (note: this requires share counts, which we don't track — fall back to "you have N tickers, here's what equal-weighting would give you per name; flag anything over 10%" using equal-weight assumption, with a clear caveat)
- [ ] Decide before implementing: do we add optional share counts here, or stay strictly equal-weight? Log decision in DECISIONS.md.

### 4.2 Portfolio check view
- [ ] `src/views/portfolio_check.py`: render the three checks as cards
- [ ] Header banner: "This is a quick sanity check, not a tracking tool. For full portfolio tracking with multi-currency, dividends, and tax reporting, use Sharesight or Empower."
- [ ] Wire into `app.py` sidebar nav

### 4.3 Polish pass
- [ ] Empty states on every view (no holdings, no observations active, no journal entries)
- [ ] Stale data banners with "last updated" timestamps
- [ ] Consistent number formatting throughout
- [ ] Sidebar footer with full disclaimer text (from CLAUDE.md)
- [ ] All charts/heatmaps use accessible color schemes (text labels not color alone)
- [ ] Network failure handling tested by simulating offline (e.g. `--no-network` mode in dev)

### 4.4 Documentation
- [ ] `README.md`: project description, what it does, what it intentionally doesn't, install/run instructions
- [ ] In-app "About" expander explaining the philosophy

### 4.5 Phase 4 review checkpoint
- [ ] All tests pass
- [ ] App handles offline gracefully
- [ ] Portfolio check renders with real holdings
- [ ] User can complete a real decision flow end-to-end and feel that the friction was useful

---

## Backlog (post-v1)

These are not commitments — they're notes for if the tool proves useful enough to extend:

- **Backtest stats by market regime:** show how observations have performed in bull vs bear vs flat markets specifically on this ticker
- **Decision journal analytics:** "you've ignored 7 'do_nothing' actions and bought anyway — outcomes were…"
- **Multi-ticker observation scan:** show all active observations across watchlist in one list (read-only, not a dashboard)
- **CSV import of holdings from Sharesight/Empower exports** — for users who want quick portfolio check without re-entering data
