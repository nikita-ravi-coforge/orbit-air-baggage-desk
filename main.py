"""Command line for the baggage desk.

This is the only file that reads the clock. It parses arguments, picks "now", opens the
database, calls claims.py, and prints. It holds no rule logic.
"""

import argparse
import csv
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime

import claims
import db

SEED_COLUMNS = ("passenger", "flight", "type", "tier", "note")


def build_parser():
    parser = argparse.ArgumentParser(prog="main.py", description="Orbit Air baggage desk")
    parser.add_argument("--now", help="ISO time to use instead of the real clock")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("file", help="file a new claim")
    p.add_argument("passenger")
    p.add_argument("flight")
    p.add_argument("type")
    p.add_argument("tier")
    p.add_argument("note", nargs="?", default=None)

    p = sub.add_parser("list", help="list claims")
    p.add_argument("--status", choices=claims.STATUSES)
    p.add_argument("--tier", choices=claims.TIERS)

    p = sub.add_parser("assign", help="assign a claim to an agent")
    p.add_argument("id", type=int)
    p.add_argument("agent")

    for name in ("resolve", "close", "history"):
        p = sub.add_parser(name, help=f"{name} a claim")
        p.add_argument("id", type=int)

    sub.add_parser("escalate", help="escalate every overdue claim")

    p = sub.add_parser("seed", help="file claims from a CSV")
    p.add_argument("csv")

    return parser


def pick_now(now_arg):
    if now_arg is not None:
        now = datetime.fromisoformat(now_arg)
        if now.tzinfo is not None:
            raise ValueError("--now must not include a timezone offset")
        return now
    return datetime.now().replace(microsecond=0)


def run(conn, args, now):
    if args.command == "file":
        claim_id = claims.file_claim(
            conn,
            passenger=args.passenger,
            flight=args.flight,
            claim_type=args.type,
            tier=args.tier,
            note=args.note or None,
            now=now,
        )
        print(f"filed claim {claim_id}")
    elif args.command == "list":
        for c in claims.list_claims(conn, status=args.status, tier=args.tier):
            print("  ".join(str(v) for v in (
                c["id"], c["passenger"], c["flight"], c["type"], c["tier"],
                c["status"], c["agent"] or "-", c["deadline"],
            )))
    elif args.command == "assign":
        claims.assign(conn, args.id, args.agent, now)
        print(f"assigned claim {args.id} to {args.agent}")
    elif args.command == "resolve":
        claims.resolve(conn, args.id, now)
        print(f"resolved claim {args.id}")
    elif args.command == "close":
        claims.close(conn, args.id, now)
        print(f"closed claim {args.id}")
    elif args.command == "escalate":
        ids = claims.escalate(conn, now)
        if not ids:
            print("no claims escalated")
        for claim_id in ids:
            print(f"escalated {claim_id}")
    elif args.command == "history":
        for h in claims.get_history(conn, args.id):
            print(
                f"{h['changed_at']}  {h['old_status'] or '-'}  -> {h['new_status']}  "
                f"by {h['changed_by']}"
            )
    elif args.command == "seed":
        count = 0
        with open(args.csv, newline="") as f:
            reader = csv.DictReader(f)
            missing = [c for c in SEED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"CSV header is missing: {', '.join(missing)}")
            # The header is row 1, so the first claim is row 2, as in a spreadsheet.
            for row_number, row in enumerate(reader, start=2):
                try:
                    claims.file_claim(
                        conn,
                        passenger=row["passenger"],
                        flight=row["flight"],
                        claim_type=row["type"],
                        tier=row["tier"],
                        note=row["note"] or None,
                        now=now,
                    )
                except ValueError as exc:
                    raise ValueError(f"row {row_number}: {exc}") from exc
                count += 1
        print(f"seeded {count} claims")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        now = pick_now(args.now)
        with closing(db.connect(os.environ.get("ORBIT_DB", "baggage.db"))) as conn:
            run(conn, args, now)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
