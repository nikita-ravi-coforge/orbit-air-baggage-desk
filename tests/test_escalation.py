import sqlite3
from datetime import datetime

import pytest

import claims

FILED = datetime(2026, 11, 2, 10, 0, 0)
FILED_AT = "2026-11-02T10:00:00"
# A gold claim filed at 10:00 has a deadline of 14:00 the same day.
BEFORE_DEADLINE = datetime(2026, 11, 2, 13, 59, 0)
AT_DEADLINE = datetime(2026, 11, 2, 14, 0, 0)
AFTER_DEADLINE = datetime(2026, 11, 2, 14, 1, 0)
AFTER_DEADLINE_AT = "2026-11-02T14:01:00"
# Every change made before the sweep happens before the deadline.
ASSIGN_TIME = datetime(2026, 11, 2, 11, 0, 0)
RESOLVE_TIME = datetime(2026, 11, 2, 12, 0, 0)
CLOSE_TIME = datetime(2026, 11, 2, 13, 0, 0)
AGENT = "Priya Nair"

FAIL_HISTORY_TRIGGER = """
CREATE TRIGGER fail_history
BEFORE INSERT ON history
BEGIN
  SELECT RAISE(ABORT, 'history failed');
END;
"""


def file_gold_claim(conn):
    return claims.file_claim(
        conn,
        passenger="Asha Rao",
        flight="OA101",
        claim_type="lost",
        tier="gold",
        note=None,
        now=FILED,
    )


def status_of(conn, claim_id):
    return claims.get_claim(conn, claim_id)["status"]


def bring_to(conn, claim_id, status):
    # Reach each status through the real commands, not SQL.
    if status in ("assigned", "resolved", "closed"):
        claims.assign(conn, claim_id, AGENT, ASSIGN_TIME)
    if status in ("resolved", "closed"):
        claims.resolve(conn, claim_id, RESOLVE_TIME)
    if status == "closed":
        claims.close(conn, claim_id, CLOSE_TIME)


@pytest.mark.parametrize(
    ("now", "expected_status", "expect_escalated"),
    [
        (BEFORE_DEADLINE, "open", False),
        (AT_DEADLINE, "open", False),
        (AFTER_DEADLINE, "escalated", True),
    ],
    ids=["13:59", "14:00", "14:01"],
)
def test_overdue_edges(conn, now, expected_status, expect_escalated):
    claim_id = file_gold_claim(conn)

    escalated = claims.escalate(conn, now)

    assert escalated == ([claim_id] if expect_escalated else [])
    assert status_of(conn, claim_id) == expected_status


def test_escalate_overdue_open_and_assigned(conn):
    open_id = file_gold_claim(conn)
    assigned_id = file_gold_claim(conn)
    claims.assign(conn, assigned_id, AGENT, ASSIGN_TIME)

    escalated = claims.escalate(conn, AFTER_DEADLINE)

    assert escalated == [open_id, assigned_id]
    assert status_of(conn, open_id) == "escalated"
    assert status_of(conn, assigned_id) == "escalated"


@pytest.mark.parametrize(
    ("status", "sweep_at"),
    [
        ("resolved", AFTER_DEADLINE),
        ("closed", AFTER_DEADLINE),
        ("open", BEFORE_DEADLINE),
        ("assigned", BEFORE_DEADLINE),
    ],
    ids=["overdue-resolved", "overdue-closed", "open-not-due", "assigned-not-due"],
)
def test_escalate_leaves_claim_alone(conn, status, sweep_at):
    claim_id = file_gold_claim(conn)
    bring_to(conn, claim_id, status)
    history_before = claims.get_history(conn, claim_id)

    escalated = claims.escalate(conn, sweep_at)

    assert claim_id not in escalated
    assert status_of(conn, claim_id) == status
    assert claims.get_history(conn, claim_id) == history_before


def test_escalation_writes_history(conn):
    claim_id = file_gold_claim(conn)

    claims.escalate(conn, AFTER_DEADLINE)

    history = claims.get_history(conn, claim_id)
    assert history[0] == {
        "old_status": None,
        "new_status": "open",
        "changed_by": "system",
        "changed_at": FILED_AT,
    }
    assert history[-1] == {
        "old_status": "open",
        "new_status": "escalated",
        "changed_by": "system",
        "changed_at": AFTER_DEADLINE_AT,
    }


def test_reject_escalate_that_is_not_overdue(conn):
    claim_id = file_gold_claim(conn)

    with pytest.raises(ValueError):
        claims.change_status(conn, claim_id, "escalated", "system", AT_DEADLINE)

    assert status_of(conn, claim_id) == "open"
    assert len(claims.get_history(conn, claim_id)) == 1


def test_rollback_when_history_write_fails(conn):
    claim_id = file_gold_claim(conn)
    # Install the trigger only after filing, or it would block the filing history row.
    conn.execute(FAIL_HISTORY_TRIGGER)

    with pytest.raises((sqlite3.IntegrityError, sqlite3.DatabaseError)):
        claims.assign(conn, claim_id, AGENT, ASSIGN_TIME)

    # Read back on the same connection, so an uncommitted update would still be visible.
    claim = claims.get_claim(conn, claim_id)
    assert claim["status"] == "open"
    assert claim["agent"] is None
    assert claims.get_history(conn, claim_id) == [
        {
            "old_status": None,
            "new_status": "open",
            "changed_by": "system",
            "changed_at": FILED_AT,
        }
    ]
