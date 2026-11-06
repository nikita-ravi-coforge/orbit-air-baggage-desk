from datetime import datetime

import pytest

import claims

FILED = datetime(2026, 11, 2, 10, 0, 0)
FILED_AT = "2026-11-02T10:00:00"
CHANGED = datetime(2026, 11, 2, 11, 0, 0)
CHANGED_AT = "2026-11-02T11:00:00"
AGENT = "Priya Nair"
SEEDED_AGENT = "Sam Lee"
MISSING_ID = 999


def file_claim(conn):
    return claims.file_claim(
        conn,
        passenger="Asha Rao",
        flight="OA101",
        claim_type="lost",
        tier="standard",
        note=None,
        now=FILED,
    )


def seed_status(conn, claim_id, status, agent=None):
    # The commands that reach these statuses are not all on this branch, so the test seeds them.
    with conn:
        conn.execute(
            "UPDATE claims SET status = ?, agent = ? WHERE id = ?", (status, agent, claim_id)
        )


def history_count(conn, claim_id):
    return conn.execute(
        "SELECT COUNT(*) FROM history WHERE claim_id = ?", (claim_id,)
    ).fetchone()[0]


def run_action(conn, action, claim_id):
    if action == "assign":
        return claims.assign(conn, claim_id, AGENT, CHANGED)
    if action == "resolve":
        return claims.resolve(conn, claim_id, CHANGED)
    if action == "close":
        return claims.close(conn, claim_id, CHANGED)
    raise AssertionError(f"unknown action {action!r}")


@pytest.mark.parametrize(
    ("start", "action", "expected"),
    [
        ("open", "assign", "assigned"),
        ("escalated", "assign", "assigned"),
        ("assigned", "resolve", "resolved"),
        ("escalated", "resolve", "resolved"),
        ("resolved", "close", "closed"),
    ],
    ids=[
        "open-to-assigned",
        "escalated-to-assigned",
        "assigned-to-resolved",
        "escalated-to-resolved",
        "resolved-to-closed",
    ],
)
def test_allowed_transition(conn, start, action, expected):
    claim_id = file_claim(conn)
    seeded_agent = None if action == "assign" else SEEDED_AGENT
    seed_status(conn, claim_id, start, agent=seeded_agent)
    rows_before = history_count(conn, claim_id)

    run_action(conn, action, claim_id)

    claim = claims.get_claim(conn, claim_id)
    assert claim["status"] == expected
    if action == "assign":
        assert claim["agent"] == AGENT
    else:
        # Resolve and close keep the agent already on the claim.
        assert claim["agent"] == SEEDED_AGENT

    history = claims.get_history(conn, claim_id)
    assert len(history) == rows_before + 1
    assert history[-1] == {
        "old_status": start,
        "new_status": expected,
        "changed_by": AGENT if action == "assign" else "system",
        "changed_at": CHANGED_AT,
    }


@pytest.mark.parametrize(
    ("start", "action"),
    [
        ("open", "close"),
        ("assigned", "close"),
        ("closed", "resolve"),
    ],
    ids=["open-to-closed", "assigned-to-closed", "closed-to-resolved"],
)
def test_disallowed_transition(conn, start, action):
    claim_id = file_claim(conn)
    seed_status(conn, claim_id, start)
    rows_before = history_count(conn, claim_id)

    with pytest.raises(ValueError) as excinfo:
        run_action(conn, action, claim_id)

    assert "status" in str(excinfo.value)
    assert claims.get_claim(conn, claim_id)["status"] == start
    assert history_count(conn, claim_id) == rows_before


def test_status_change_writes_history(conn):
    claim_id = file_claim(conn)

    claims.assign(conn, claim_id, AGENT, CHANGED)

    assert claims.get_history(conn, claim_id) == [
        {
            "old_status": None,
            "new_status": "open",
            "changed_by": "system",
            "changed_at": FILED_AT,
        },
        {
            "old_status": "open",
            "new_status": "assigned",
            "changed_by": AGENT,
            "changed_at": CHANGED_AT,
        },
    ]
    assert claims.get_claim(conn, claim_id)["agent"] == AGENT


@pytest.mark.parametrize(
    "call",
    [
        lambda conn: claims.assign(conn, MISSING_ID, AGENT, CHANGED),
        lambda conn: claims.resolve(conn, MISSING_ID, CHANGED),
        lambda conn: claims.close(conn, MISSING_ID, CHANGED),
        lambda conn: claims.get_history(conn, MISSING_ID),
    ],
    ids=["assign", "resolve", "close", "history"],
)
def test_unknown_claim_raises(conn, call):
    with pytest.raises(ValueError) as excinfo:
        call(conn)

    assert str(MISSING_ID) in str(excinfo.value)
