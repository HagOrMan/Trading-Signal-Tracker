# CLAUDE.md — Instructions for Claude Code

> Read this on every session. Then check PROGRESS.md for what to build next.
> Read SPEC.md to understand *why* something is designed a certain way.
> Log architectural forks in DECISIONS.md — never re-litigate a settled decision.

---

## What This App Is

The Anti-Signal Tool: a small, opinionated decision-support tool. When the user is about to make an investment decision, this tool slows them down, surfaces relevant observations on the asset, shows how those observations have *historically played out on that specific ticker*, and walks them through a research checklist before they act.

It is **not** a portfolio dashboard, charting tool, or signal generator. It is a decision speed bump with a built-in honesty layer.

---

## The Three Core Constraints

**1. No buy/sell signals — observations only.**
Every place where a pattern is detected and shown must follow the three-part observation format defined in SPEC.md §6.2. Do not add BUY/SELL labels, score-based rankings, or directional trade recommendations anywhere — even if it seems helpful. The framing text lives in `src/observation_templates.py` and is hand-written, not generated. If you find yourself wanting to write code that picks "the best time to buy" — stop, that's not what this tool does.

**2. The honesty layer must be honest.**
When the user views observations on a ticker, the honesty layer (§6.3) shows how those observations have historically played out *on that specific ticker*. If a popular pattern (e.g. golden cross) has historically preceded *negative* returns on a given ticker, the UI must show that clearly. Do not filter, weight, or massage the historical data to make observations look more useful than they are. The whole point is to undermine signals that don't deserve trust.

**3. Stay small.**
This is a four-phase tool, not a platform. Resist scope creep. If a feature request would duplicate functionality available in Yahoo Finance, Sharesight, Empower, or Finviz, the answer is "use that tool." See SPEC.md §3 for the explicit list of things this tool intentionally does not do.

---

## How to Work

### Starting a session
1. Read this file (CLAUDE.md)
2. Read PROGRESS.md — find current phase, find first unchecked task
3. If task touches an existing module, read that module before writing
4. Build, test, mark complete, move on

### When uncertain about scope
- Check SPEC.md for intent
- Check DECISIONS.md for settled choices
- Do **not** invent scope outside SPEC.md or PROGRESS.md
- If a genuine fork appears, add it to DECISIONS.md "Pending" section and flag it

### Task size
- Each PROGRESS.md task is meant to be completable in one focused session
- If too large, split it and update PROGRESS.md before starting

---

## Coding Standards

### General
- Python 3.11+
- Type hints on all function signatures
- One-line docstring on every public function (args/returns if non-obvious)
- No unused imports
- Prefer many small functions over fewer large ones

### Streamlit
- All state via `st.session_state` — no module-level globals
- Cache expensive operations with `@st.cache_data(ttl=3600)` (1 hour — daily-fresh data is fine)
- View files (`src/views/*.py`) are thin: one `render()` function, calls into `src/`, no business logic
- No auto-refresh loops — this is not a dashboard

### Data & caching
- All yfinance calls go through `src/data_fetch.py` — nowhere else
- All SQLite access goes through the appropriate module — no raw SQL in views
- Parameterized queries only, never f-string SQL
- Cache reads always before network calls; network calls update cache

### Error handling
- Network failures must never crash the app — catch in `data_fetch.py`, return empty DataFrame, view renders stale-data warning
- Missing data shows informative empty state, not stack trace
- Use Python `logging`, not `print`

### Testing
- Every function in `src/` gets at least one test in `tests/`
- Use `pytest`
- Mock yfinance calls in tests — never make real network calls in the suite
- Honesty layer functions especially need tests with synthetic price series that have known forward returns

---

## Approved Libraries

| Library | Use |
|---|---|
| `streamlit` | UI |
| `yfinance` | Market data |
| `pandas` | Data manipulation + indicators (MA / vol / max-min / corr inline) |
| `plotly` | Charts (used sparingly for honesty-layer histograms) |
| `sqlite3` | Storage (stdlib — no ORM) |
| `tomllib` | Config parsing (stdlib, Python 3.11+) |
| `pytest` | Testing |

**Do not add:** ORMs, ML libraries (sklearn/torch/tensorflow), additional HTTP clients, dashboard frameworks beyond Streamlit. New deps require an entry in DECISIONS.md.

---

## Settled Design Decisions (full detail in DECISIONS.md)

- No buy/sell signals. Observations only.
- TSX tickers use `.TO` suffix at fetch time; `utils.normalize_ticker()` handles it
- Adjusted close for all return calculations
- SQLite only — no ORM
- Config in `config.toml`
- yfinance is the only data source in v1
- Observation framing text is hand-written and lives in `observation_templates.py`
- Honesty layer is per-ticker historical, not generic — and shows negative results honestly

---

## File Roles

| File | Responsibility |
|---|---|
| `app.py` | Entry point: page routing, sidebar |
| `config.toml` | User profile, thresholds |
| `src/data_fetch.py` | yfinance + cache |
| `src/indicators.py` | Pure functions: MA, vol, drawdown, correlation |
| `src/observations.py` | Detector functions per observation type |
| `src/observation_templates.py` | Hand-written framing text per observation type |
| `src/honesty_layer.py` | Historical backtest of observations on a single ticker |
| `src/checklist.py` | Research checklist + decision journal |
| `src/advice.py` | Personalized portfolio check |
| `src/portfolio.py` | Holdings/watchlist CRUD, schema |
| `src/utils.py` | Ticker normalization, formatting |
| `src/views/*.py` | One `render()` per view, UI only |

---

## What Not To Do

- Do not add features outside SPEC.md or PROGRESS.md without flagging
- Do not write business logic in view files
- Do not make yfinance calls outside `data_fetch.py`
- Do not use module-level globals as state
- Do not add dependencies without updating `requirements.txt` and DECISIONS.md
- Do not use raw f-string SQL
- Do not generate buy/sell language anywhere
- Do not skip the three-part observation format
- Do not filter or weight historical data in the honesty layer to make observations look better
- Do not build dashboard-style auto-refresh — this is not a dashboard
- Do not duplicate functionality of Yahoo Finance, Sharesight, Empower, or Finviz

---

## Disclaimers (must appear in app)

In sidebar footer and on every page where observations or advice are shown:

> This tool is for personal informational use only and does not constitute financial advice.
> Observations are data patterns worth researching — not buy/sell recommendations.
> The honesty layer shows historical patterns on a single ticker; past performance does not predict future results.
> Market data is end-of-day and may be delayed.
> For full portfolio tracking and charting, use Sharesight, Empower, or Yahoo Finance.
