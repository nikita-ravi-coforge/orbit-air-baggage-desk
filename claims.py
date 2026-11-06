"""Claim rules for the baggage desk.

Nothing here reads the clock. Any function that needs the current time takes it as `now`.
"""

from datetime import datetime, timedelta

CLAIM_TYPES = ("delayed", "lost", "damaged")
TIERS = ("standard", "silver", "gold")
STATUSES = ("open", "assigned", "escalated", "resolved", "closed")
TIER_HOURS = {"gold": 4, "silver": 24, "standard": 72}
SYSTEM = "system"
ALLOWED_CHANGES = {
    "open": {"assigned", "escalated"},
    "assigned": {"resolved", "escalated"},
    "escalated": {"assigned", "resolved"},
    "resolved": {"closed"},
    "closed": set(),
}

CLAIM_COLUMNS = (
    "id, passenger, flight, type, tier, status, agent, note, filed_at, deadline"
)
HISTORY_COLUMNS = "old_status, new_status, changed_by, changed_at"


def _format_time(dt):
    return dt.isoformat(timespec="seconds")


def _validate_filing(passenger, flight, claim_type, tier):
    if passenger is None or not passenger.strip():
        raise ValueError("passenger must not be empty")
    if flight is None or not flight.strip():
        raise ValueError("flight must not be empty")
    if claim_type not in CLAIM_TYPES:
        raise ValueError(f"type must be one of {', '.join(CLAIM_TYPES)}, got {claim_type!r}")
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {', '.join(TIERS)}, got {tier!r}")


def compute_deadline(filed_at, tier):
    """Return the deadline for a claim filed at filed_at with the given tier."""
    return filed_at + timedelta(hours=TIER_HOURS[tier])


def is_overdue(deadline_text, now):
    """Return True only if now is strictly later than the stored deadline."""
    return now > datetime.fromisoformat(deadline_text)


def file_claim(conn, *, passenger, flight, claim_type, tier, note=None, now):
    """File a new open claim and its first history row in one transaction. Return its id."""
    _validate_filing(passenger, flight, claim_type, tier)
    filed_at = _format_time(now)
    deadline = _format_time(compute_deadline(now, tier))

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO claims (passenger, flight, type, tier, status, agent, note,
                                filed_at, deadline)
            VALUES (?, ?, ?, ?, 'open', NULL, ?, ?, ?)
            """,
            (passenger.strip(), flight.strip(), claim_type, tier, note, filed_at, deadline),
        )
        claim_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
            VALUES (?, NULL, 'open', ?, ?)
            """,
            (claim_id, SYSTEM, filed_at),
        )
    return claim_id


def get_claim(conn, claim_id):
    """Return the claim as a dict. Raise ValueError naming the id if it does not exist."""
    row = conn.execute(
        f"SELECT {CLAIM_COLUMNS} FROM claims WHERE id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"claim {claim_id} not found")
    return dict(row)


def get_history(conn, claim_id):
    """Return the claim's history rows as dicts, oldest first. Raise ValueError if unknown."""
    get_claim(conn, claim_id)
    rows = conn.execute(
        f"SELECT {HISTORY_COLUMNS} FROM history WHERE claim_id = ? ORDER BY id",
        (claim_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def change_status(conn, claim_id, new_status, changed_by, now, agent=None):
    """Move a claim to new_status and record it in history, in one transaction.

    This is the only function that reads ALLOWED_CHANGES. If agent is given, it is set
    in the same UPDATE as the status. Raise ValueError naming the id if the claim does
    not exist, or ValueError mentioning status if the move is not allowed. On any error
    nothing is written.
    Raise ValueError if new_status is "escalated" and the claim is not overdue at now.
    """
    changed_at = _format_time(now)
    with conn:
        row = conn.execute(
            "SELECT status, deadline FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"claim {claim_id} not found")
        old_status = row["status"]
        if new_status not in ALLOWED_CHANGES[old_status]:
            raise ValueError(
                f"cannot change status of claim {claim_id} from {old_status!r} "
                f"to {new_status!r}"
            )
        if new_status == "escalated" and not is_overdue(row["deadline"], now):
            raise ValueError(
                f"cannot escalate claim {claim_id}: not overdue "
                f"(deadline {row['deadline']})"
            )

        if agent is None:
            conn.execute(
                "UPDATE claims SET status = ? WHERE id = ?", (new_status, claim_id)
            )
        else:
            conn.execute(
                "UPDATE claims SET status = ?, agent = ? WHERE id = ?",
                (new_status, agent, claim_id),
            )
        conn.execute(
            """
            INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (claim_id, old_status, new_status, changed_by, changed_at),
        )


def assign(conn, claim_id, agent, now):
    """Assign the claim to agent. The agent is recorded as the one who made the change."""
    change_status(conn, claim_id, "assigned", agent, now, agent=agent)


def resolve(conn, claim_id, now):
    """Mark the claim resolved, keeping its agent."""
    change_status(conn, claim_id, "resolved", SYSTEM, now)


def close(conn, claim_id, now):
    """Close a resolved claim, keeping its agent."""
    change_status(conn, claim_id, "closed", SYSTEM, now)


def escalate(conn, now):
    """Escalate every overdue open or assigned claim, one transaction per claim.

    Return the ids escalated, in id order. Claims in other statuses or not yet overdue
    are left alone.
    """
    rows = conn.execute(
        "SELECT id, deadline FROM claims WHERE status IN ('open', 'assigned') ORDER BY id"
    ).fetchall()
    escalated = []
    for row in rows:
        if is_overdue(row["deadline"], now):
            change_status(conn, row["id"], "escalated", SYSTEM, now)
            escalated.append(row["id"])
    return escalated


def list_claims(conn, status=None, tier=None):
    """Return claims as dicts ordered by id, optionally filtered by status and/or tier."""
    clauses = []
    params = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if tier is not None:
        clauses.append("tier = ?")
        params.append(tier)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {CLAIM_COLUMNS} FROM claims{where} ORDER BY id", params
    ).fetchall()
    return [dict(row) for row in rows]
