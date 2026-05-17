# PROGRESS.md — Build Tracker

> **For Claude Code:** Start here every session. Find current phase. Find first unchecked task. Read relevant source files. Build it. Check it off.
> If task is ambiguous, check SPEC.md for intent first.
> Architectural forks not covered here or in DECISIONS.md → add to DECISIONS.md "Pending" and flag.

**Current phase: complete — all four phases shipped in initial build (2026-05-17). Next session work belongs in the Backlog or a new phase.**

---

## Phase 1 — Foundation
*Goal: One ticker can be reviewed end-to-end with one observation type wired through. Proves the whole vertical works.*

### 1.1 Project scaffold
- [x] Create `requirements.txt` with pinned versions: `streamlit`, `yfinance`, `pandas`, `plotly`, `pytest` (no `tomli` — stdlib `tomllib` on 3.11+; no `pandas-ta` — see DEC-013)
- [x] Create `config.toml` with: `[user_profile]`, `[thresholds]`, `[benchmarks]`, `[honesty_layer]`
- [x] `data/` directory with `.gitkeep`; `data/*.db*` ignored in `.gitignore`
- [x] `src/__init__.py`, `src/views/__init__.py`, `tests/__init__.py`
- [x] Verified Python 3.14.2 venv + `streamlit==1.57.0` installs cleanly

### 1.2 SQLite schemas
- [x] `src/portfolio.py` — `init_db()`, schema includes optional `shares` column (DEC-012)
- [x] CRUD: `add_holding`, `remove_holding`, `get_holdings`, `update_shares`, watchlist equivalents
- [x] `src/data_fetch.py` — `init_cache_db()` schema with `prices`, `fetch_meta`, `ticker_info`
- [x] Tests: `tests/test_portfolio.py` — 9 tests, all pass

### 1.3 Ticker utilities
- [x] `src/utils.py` — `normalize_ticker`, `display_ticker`, `format_pct`, `format_currency`, `format_count`
- [x] Tests: `tests/test_utils.py` — 12 tests, all pass

### 1.4 Data fetch layer
- [x] `fetch_price_history`, `fetch_ticker_info`, `get_cache_age`, `get_latest_price` — cache-first, network failure returns cached
- [x] Tests: `tests/test_data_fetch.py` — 8 tests with mocked yfinance, all pass

### 1.5 Indicators
- [x] `moving_average`, `log_returns`, `rolling_volatility`, `rolling_max`, `rolling_min`, `drawdown_from_high`, `rolling_correlation`, `percentile_rank`, `forward_return`
- [x] Tests: `tests/test_indicators.py` — 10 tests, all pass

### 1.6 First observation — and all 7 others (Phase 2.1/2.2 done in same pass)
- [x] `src/observation_templates.py` — all 8 templates hand-written (DEC-008)
- [x] `src/observations.py` — `Observation` dataclass + all 8 detectors + `get_active_observations`
- [x] Tests: `tests/test_observations.py` — 14 tests with engineered synthetic series, all pass

### 1.7 Honesty layer (and 2.3, 2.4 done in same pass)
- [x] `src/honesty_layer.py` — `find_historical_instances`, `forward_returns`, `summarize_outcomes`, `backtest_observation`
- [x] Cache in `backtest.db` keyed on `(ticker, observation_type, last_data_date)`
- [x] DEC-011 sample tiers: `very_low`/`low`/`moderate`/`good` + tier_message
- [x] Tests: `tests/test_honesty_layer.py` — 9 tests, including engineered negative-outcome test, all pass

### 1.8 Ticker review view
- [x] `src/views/ticker_review.py` — full `render()` with observation cards + honesty panel + checklist modal
- [x] Stale-data banner, empty state, low-sample warning surfaced

### 1.9 App entry
- [x] `app.py` — sidebar nav, disclaimer footer, bootstraps all 4 DBs

### 1.10 Phase 1 review checkpoint
- [x] All tests pass (80/80)
- [ ] App runs end-to-end against a real US ticker (manual smoke test — blocked locally by curl_cffi SSL trust issue, not a code defect; see DEC-014)
- [ ] App runs end-to-end against a real TSX ticker (same — DEC-014)
- [ ] Honesty layer shows at least one *unflattering* historical case (manual verification — pending network access)
- [x] Disclaimer visible (in sidebar footer of app.py)

---

## Phase 2 — Observations + Honesty (full set)

### 2.1–2.4 — done in Phase 1 pass
- [x] All 8 detectors implemented and templated
- [x] Honesty layer handles all 8 types via `observations.find_historical_instances`
- [x] Backtest cache invalidation by `last_data_date` key — extending price history busts the cache automatically
- [x] DEC-011 tiers wired into the UI (`_render_honesty_panel`)

### 2.5 Phase 2 review checkpoint
- [x] All 8 detectors tested (unit tests use engineered synthetic series)
- [x] Templates read naturally — hand-written, no robotic placeholders
- [x] Honesty layer renders for all 8 types in `ticker_review.py`
- [ ] Manual confirmation that at least one ticker shows multiple simultaneous active observations (pending network access)

---

## Phase 3 — Checklist + Journal

### 3.1 Decision journal schema
- [x] `src/checklist.py` — `init_decisions_db()`, schema matches SPEC §6.4
- [x] CRUD: `save_journal_entry`, `get_all_entries`, `get_entries_for_ticker`, `get_entries_older_than`, `get_entries_within_days`, `delete_entry`

### 3.2 Research checklist component
- [x] `CHECKLIST_ITEMS` constant (6 items, SPEC §6.4 phrasing)
- [x] `_checklist_dialog` rendered in `ticker_review.py` — checkboxes, required note, action radio, save button
- [x] Submission saves observations snapshot + checklist state + note + action + price-at-decision

### 3.3 Journal review page
- [x] `src/views/journal.py` — three tabs: Recent / Old-enough-to-review / All entries
- [x] Each entry shows ticker, action, observations active at the time, note, return-since
- [x] Tests: `tests/test_checklist.py` — 6 tests, all pass (including `get_entries_older_than` with backdated entry)

### 3.4 Navigation
- [x] `app.py` sidebar nav: Review a ticker | Holdings & watchlist | Portfolio check | Decision journal

### 3.5 Phase 3 review checkpoint
- [x] All tests pass
- [ ] Manual end-to-end flow (review → checklist → save → journal) — pending network access for live ticker fetch
- [x] Old-enough-to-review tab verified by `test_get_entries_older_than` with backdated insert

---

## Phase 4 — Portfolio Check + Polish

### 4.1 Personalized portfolio check
- [x] `src/advice.py` — `WeightedHolding`, `PortfolioObservation`, three checks + `run_all_checks`
- [x] Uses real dollar weights when shares present; equal-weight fallback with banner (DEC-012)

### 4.2 Portfolio check view
- [x] `src/views/portfolio_check.py` — three check cards with severity icons + the Sharesight/Empower banner
- [x] Wired into `app.py` sidebar nav

### 4.3 Polish
- [x] Empty states across all views ("no active observations", "no holdings yet", "no journal entries", etc.)
- [x] Stale-data banner with cache age in `ticker_review.py`
- [x] Sidebar footer carries the full disclaimer from CLAUDE.md
- [x] Network-failure paths tested via `test_fetch_price_history_network_failure_returns_cached`
- [ ] Accessibility audit of color schemes (kept to text + emoji indicators; no information conveyed by color alone)

### 4.4 Documentation
- [ ] `README.md` — *not yet written; CLAUDE.md / SPEC.md / DECISIONS.md serve as project docs internally*
- [x] In-app "About this tool" expander in the sidebar

### 4.5 Phase 4 review checkpoint
- [x] All tests pass (80/80)
- [x] App handles offline gracefully (verified in `test_fetch_price_history_network_failure_returns_cached`)
- [ ] Portfolio check rendered against real holdings (pending network access)
- [ ] User-felt decision-flow review (subjective — owner-only)

---

## Open items (carried over to next session)

1. **Local network setup.** `curl_cffi` cannot find a CA bundle on this Windows install — yfinance fetches fail with SSL trust errors. Likely fix: set `CURL_CA_BUNDLE=$(python -c "import certifi;print(certifi.where())")` in the user's shell, or upgrade/patch `curl_cffi`. The app handles the failure gracefully but cannot be live-smoke-tested until this is resolved.
2. **README.md.** Worth writing once a real session has confirmed end-to-end behavior. Don't write it until the screenshots will be real.
3. **Phase-1 unflattering-case demonstration.** Once network works, pick a ticker (e.g. a meme stock or a banged-up cyclical) and verify the honesty layer surfaces a negative median — confirms DEC-009 isn't being subtly violated by any code path.

---

## Backlog (post-v1)

These are not commitments — notes for if the tool proves useful enough to extend:

- **Backtest stats by market regime:** show how observations have performed in bull vs bear vs flat markets specifically on this ticker
- **Decision journal analytics:** "you've ignored 7 'do_nothing' actions and bought anyway — outcomes were…"
- **Multi-ticker observation scan:** show all active observations across watchlist in one list (read-only, not a dashboard)
- **CSV import of holdings from Sharesight/Empower exports** — for users who want a quick portfolio check without re-entering data
- **`curl_cffi` SSL fallback** in `data_fetch.py` — auto-set `CURL_CA_BUNDLE` from certifi if not already set
