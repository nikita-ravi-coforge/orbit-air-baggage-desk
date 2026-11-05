import sqlite3
from datetime import datetime

import pytest

import claims

NOW = datetime(2026, 11, 2, 10, 0, 0)
FILED_AT = "2026-11-02T10:00:00"


def file_claim(conn, **overrides):
    fields = {
        "passenger": "Asha Rao",
        "flight": "OA101",
        "claim_type": "lost",
        "tier": "standard",
        "note": None,
        "now": NOW,
    }
    fields.update(overrides)
    return claims.file_claim(conn, **fields)


def insert_claim(conn, **overrides):
    row = {
        "passenger": "Asha Rao",
        "flight": "OA101",
        "type": "lost",
        "tier": "standard",
        "status": "open",
        "filed_at": FILED_AT,
        "deadline": "2026-11-05T10:00:00",
    }
    row.update(overrides)
    conn.execute(
        """
        INSERT INTO claims (passenger, flight, type, tier, status, filed_at, deadline)
        VALUES (:passenger, :flight, :type, :tier, :status, :filed_at, :deadline)
        """,
        row,
    )


def count_rows(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def ids(rows):
    return [row["id"] for row in rows]


def test_file_claim_starts_open(conn):
    claim_id = file_claim(
        conn,
        passenger="Asha Rao",
        flight="OA101",
        claim_type="damaged",
        tier="silver",
        note="Handle broken",
    )

    claim = claims.get_claim(conn, claim_id)

    assert set(claim) == {
        "id",
        "passenger",
        "flight",
        "type",
        "tier",
        "status",
        "agent",
        "note",
        "filed_at",
        "deadline",
    }
    assert claim["id"] == claim_id
    assert claim["passenger"] == "Asha Rao"
    assert claim["flight"] == "OA101"
    assert claim["type"] == "damaged"
    assert claim["tier"] == "silver"
    assert claim["note"] == "Handle broken"
    assert claim["status"] == "open"
    assert claim["agent"] is None
    assert claim["filed_at"] == FILED_AT

    # An omitted note is stored as NULL, not as an empty string.
    no_note_id = file_claim(conn, note=None)
    assert claims.get_claim(conn, no_note_id)["note"] is None


@pytest.mark.parametrize(
    ("tier", "expected_deadline"),
    [
        ("gold", "2026-11-02T14:00:00"),
        ("silver", "2026-11-03T10:00:00"),
        ("standard", "2026-11-05T10:00:00"),
    ],
)
def test_deadline_matches_tier(conn, tier, expected_deadline):
    claim_id = file_claim(conn, tier=tier)

    assert claims.get_claim(conn, claim_id)["deadline"] == expected_deadline


@pytest.mark.parametrize(
    ("field", "overrides"),
    [
        ("passenger", {"passenger": "   "}),
        ("flight", {"flight": ""}),
        ("type", {"claim_type": "stolen"}),
        ("tier", {"tier": "platinum"}),
    ],
    ids=["passenger", "flight", "type", "tier"],
)
def test_reject_invalid_filing(conn, field, overrides):
    with pytest.raises(ValueError) as excinfo:
        file_claim(conn, **overrides)

    assert field in str(excinfo.value)
    assert count_rows(conn, "claims") == 0
    assert count_rows(conn, "history") == 0


def test_filing_writes_history(conn):
    claim_id = file_claim(conn)

    assert claims.get_history(conn, claim_id) == [
        {
            "old_status": None,
            "new_status": "open",
            "changed_by": "system",
            "changed_at": FILED_AT,
        }
    ]


def test_list_filters_by_status_and_tier(conn):
    gold_open = file_claim(conn, tier="gold")
    gold_assigned = file_claim(conn, tier="gold")
    silver_open = file_claim(conn, tier="silver")
    silver_assigned = file_claim(conn, tier="silver")
    # The assign command arrives on a later branch, so the test seeds this status.
    with conn:
        conn.execute(
            "UPDATE claims SET status = 'assigned' WHERE id IN (?, ?)",
            (gold_assigned, silver_assigned),
        )

    all_claims = claims.list_claims(conn)

    assert all(isinstance(row, dict) for row in all_claims)
    assert ids(all_claims) == [gold_open, gold_assigned, silver_open, silver_assigned]
    assert ids(claims.list_claims(conn, status="assigned")) == [gold_assigned, silver_assigned]
    assert ids(claims.list_claims(conn, tier="gold")) == [gold_open, gold_assigned]
    assert ids(claims.list_claims(conn, status="open", tier="silver")) == [silver_open]


@pytest.mark.parametrize(
    ("column", "bad_value"),
    [
        ("type", "stolen"),
        ("tier", "platinum"),
        ("status", "archived"),
    ],
    ids=["type", "tier", "status"],
)
def test_check_constraint_rejects(conn, column, bad_value):
    # A valid row must insert first, so the only cause of the failure below is the bad value.
    insert_claim(conn)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_claim(conn, **{column: bad_value})