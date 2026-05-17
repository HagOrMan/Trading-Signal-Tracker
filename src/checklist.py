"""Research checklist + decision journal storage.

This is the friction layer — the actual reason the tool exists (SPEC §6.4).
Six items, one note, one planned action. Saved to decisions.db with the active
observations frozen in JSON so a future "review old entries" page can show the
exact context the user was looking at when they decided.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "decisions.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS journal (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    date                       TEXT NOT NULL,
    ticker                     TEXT NOT NULL,
    exchange                   TEXT NOT NULL,
    active_observations_json   TEXT NOT NULL,
    checklist_state_json       TEXT NOT NULL,
    decision_note              TEXT NOT NULL,
    action_planned             TEXT NOT NULL,
    price_at_decision          REAL
);

CREATE INDEX IF NOT EXISTS idx_journal_ticker ON journal (ticker);
CREATE INDEX IF NOT EXISTS idx_journal_date   ON journal (date);
"""

CHECKLIST_ITEMS = [
    "I have checked recent news, earnings, or filings for this company.",
    "I can name *why* this pattern is appearing — fundamentals, sentiment, or macro.",
    "This fits my long-term plan; I'm not reacting to short-term noise.",
    "I have an exit plan — I know what would change my mind later.",
    "This is within my normal rebalancing schedule (or I've explicitly decided to deviate).",
    "I have looked at the honesty layer above, and the historical record supports my read.",
]

ACTIONS = ["buy", "sell", "hold", "research_more", "do_nothing"]


@dataclass(frozen=True)
class JournalEntry:
    id: int
    date: str
    ticker: str
    exchange: str
    active_observations: list[dict]
    checklist_state: dict[str, bool]
    decision_note: str
    action_planned: str
    price_at_decision: float | None


@contextmanager
def _connect(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_decisions_db(db_path: Path | str | None = None) -> None:
    """Create the journal schema. Idempotent."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_entry(r: sqlite3.Row) -> JournalEntry:
    return JournalEntry(
        id=r["id"],
        date=r["date"],
        ticker=r["ticker"],
        exchange=r["exchange"],
        active_observations=json.loads(r["active_observations_json"]),
        checklist_state=json.loads(r["checklist_state_json"]),
        decision_note=r["decision_note"],
        action_planned=r["action_planned"],
        price_at_decision=r["price_at_decision"],
    )


def save_journal_entry(
    ticker: str,
    exchange: str,
    active_observations: list[dict],
    checklist_state: dict[str, bool],
    decision_note: str,
    action_planned: str,
    price_at_decision: float | None = None,
    db_path: Path | str | None = None,
    date_override: str | None = None,
) -> int:
    """Persist one journal entry. Returns the new row id.

    `active_observations` is a list of dicts (one per observation that was active
    when the user looked at the ticker). Stored as JSON so future views can
    render exactly what the user was looking at.
    """
    if action_planned not in ACTIONS:
        raise ValueError(f"action_planned must be one of {ACTIONS}, got {action_planned!r}")
    if not decision_note.strip():
        raise ValueError("decision_note must not be empty")
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO journal "
            "(date, ticker, exchange, active_observations_json, "
            " checklist_state_json, decision_note, action_planned, price_at_decision) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                date_override or _now_iso(),
                ticker.strip().upper(),
                exchange.strip().upper(),
                json.dumps(active_observations, default=str),
                json.dumps(checklist_state),
                decision_note.strip(),
                action_planned,
                price_at_decision,
            ),
        )
    return int(cur.lastrowid)


def get_all_entries(db_path: Path | str | None = None) -> list[JournalEntry]:
    """Return all journal entries, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM journal ORDER BY date DESC"
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def get_entries_for_ticker(
    ticker: str, db_path: Path | str | None = None
) -> list[JournalEntry]:
    """Return all journal entries for a single ticker, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM journal WHERE ticker = ? ORDER BY date DESC",
            (ticker.strip().upper(),),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def get_entries_older_than(
    months: int, db_path: Path | str | None = None
) -> list[JournalEntry]:
    """Return journal entries older than `months` months. Useful for the review tab."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM journal WHERE date <= datetime('now', ?) ORDER BY date DESC",
            (f"-{int(months)} months",),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def get_entries_within_days(
    days: int, db_path: Path | str | None = None
) -> list[JournalEntry]:
    """Return journal entries from the last `days` days, newest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM journal WHERE date >= datetime('now', ?) ORDER BY date DESC",
            (f"-{int(days)} days",),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def delete_entry(entry_id: int, db_path: Path | str | None = None) -> int:
    """Remove one journal entry by id. Returns rows deleted."""
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM journal WHERE id = ?", (entry_id,))
        return cur.rowcount
