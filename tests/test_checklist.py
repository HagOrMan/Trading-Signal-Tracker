"""Tests for src.checklist — journal entry CRUD."""
from __future__ import annotations

import pytest

from src import checklist as cl


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "decisions.db"
    cl.init_decisions_db(db_path=path)
    return path


def _sample_obs() -> list[dict]:
    return [
        {
            "type": "drawdown_significant",
            "headline": "AAPL down 20%",
            "what_happened": "Drawdown.",
        }
    ]


def test_save_and_get_journal_entry(db) -> None:
    eid = cl.save_journal_entry(
        ticker="AAPL",
        exchange="NYSE",
        active_observations=_sample_obs(),
        checklist_state={"item 1": True, "item 2": False},
        decision_note="Adding on weakness.",
        action_planned="buy",
        price_at_decision=180.0,
        db_path=db,
    )
    assert eid > 0
    entries = cl.get_all_entries(db_path=db)
    assert len(entries) == 1
    e = entries[0]
    assert e.ticker == "AAPL"
    assert e.action_planned == "buy"
    assert e.price_at_decision == 180.0
    assert e.active_observations == _sample_obs()
    assert e.checklist_state["item 1"] is True


def test_save_requires_decision_note(db) -> None:
    with pytest.raises(ValueError):
        cl.save_journal_entry(
            ticker="AAPL",
            exchange="NYSE",
            active_observations=[],
            checklist_state={},
            decision_note="   ",
            action_planned="buy",
            db_path=db,
        )


def test_save_rejects_unknown_action(db) -> None:
    with pytest.raises(ValueError):
        cl.save_journal_entry(
            ticker="AAPL",
            exchange="NYSE",
            active_observations=[],
            checklist_state={},
            decision_note="Note.",
            action_planned="invest",  # not in ACTIONS
            db_path=db,
        )


def test_get_entries_for_ticker(db) -> None:
    cl.save_journal_entry("AAPL", "NYSE", [], {}, "n1", "buy", db_path=db)
    cl.save_journal_entry("MSFT", "NASDAQ", [], {}, "n2", "buy", db_path=db)
    cl.save_journal_entry("AAPL", "NYSE", [], {}, "n3", "sell", db_path=db)
    apple = cl.get_entries_for_ticker("AAPL", db_path=db)
    assert {e.decision_note for e in apple} == {"n1", "n3"}


def test_get_entries_older_than(db) -> None:
    cl.save_journal_entry(
        "AAPL", "NYSE", [], {}, "old", "buy", db_path=db, date_override="2020-01-01T00:00:00"
    )
    cl.save_journal_entry("MSFT", "NASDAQ", [], {}, "new", "buy", db_path=db)
    old = cl.get_entries_older_than(6, db_path=db)
    assert {e.decision_note for e in old} == {"old"}


def test_delete_entry(db) -> None:
    eid = cl.save_journal_entry("AAPL", "NYSE", [], {}, "n", "buy", db_path=db)
    assert cl.delete_entry(eid, db_path=db) == 1
    assert cl.get_all_entries(db_path=db) == []
