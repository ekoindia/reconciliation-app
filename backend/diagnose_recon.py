"""
EKO Recon Diagnostic Script
============================
Run from the backend/ directory:

    python diagnose_recon.py

Or with an explicit DB path:

    python diagnose_recon.py --db /path/to/recon.db
"""

import sys
import os
import argparse

# ── Ensure the backend/ directory is on sys.path so models resolve ────────────
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

# ── Load .env (sets DATABASE_URL if present) ──────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# ── Optional --db override ────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="EKO Recon diagnostic report")
parser.add_argument("--db", help="Explicit path to recon.db (overrides DATABASE_URL / .env)")
args, _ = parser.parse_known_args()

if args.db:
    db_path = os.path.abspath(args.db)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

# ── Import app models (reads DATABASE_URL) ────────────────────────────────────
from models.database import SessionLocal, Transaction

# ── SQLAlchemy helpers ────────────────────────────────────────────────────────
from sqlalchemy import func, case, literal


# ─────────────────────────────────────────────────────────────────────────────
def section(title: str):
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def subsection(title: str):
    print(f"\n  -- {title} --")


def fmt_row(label, value, indent=4):
    print(f"{' ' * indent}{label:<45} {value}")


# ─────────────────────────────────────────────────────────────────────────────
def run_diagnostics():
    db = SessionLocal()
    try:
        # ── 1. Dump rows (fino/internal) grouped by recon_status ─────────────
        section("1. DUMP ROWS (partner=fino, side=internal) — grouped by recon_status")

        dump_counts = (
            db.query(Transaction.recon_status, func.count(Transaction.id).label("cnt"))
            .filter(Transaction.partner == "fino", Transaction.side == "internal")
            .group_by(Transaction.recon_status)
            .order_by(func.count(Transaction.id).desc())
            .all()
        )

        if not dump_counts:
            print("    [no dump rows found for partner=fino, side=internal]")
        else:
            total_dump = sum(r.cnt for r in dump_counts)
            for row in dump_counts:
                fmt_row(f"recon_status = '{row.recon_status}'", f"{row.cnt:,} rows")
            fmt_row("TOTAL", f"{total_dump:,} rows")

        # ── 2. Bank rows (fino/bank) grouped by recon_status ─────────────────
        section("2. BANK ROWS (partner=fino, side=bank) — grouped by recon_status")

        bank_counts = (
            db.query(Transaction.recon_status, func.count(Transaction.id).label("cnt"))
            .filter(Transaction.partner == "fino", Transaction.side == "bank")
            .group_by(Transaction.recon_status)
            .order_by(func.count(Transaction.id).desc())
            .all()
        )

        if not bank_counts:
            print("    [no bank rows found for partner=fino, side=bank]")
        else:
            total_bank = sum(r.cnt for r in bank_counts)
            for row in bank_counts:
                fmt_row(f"recon_status = '{row.recon_status}'", f"{row.cnt:,} rows")
            fmt_row("TOTAL", f"{total_bank:,} rows")

        # ── 3. Matched bank rows — check what their matched_with_id points to ─
        section("3. MATCHED BANK ROWS — where does matched_with_id point?")

        # Fetch all bank rows that show recon_status = 'matched'
        matched_bank_rows = (
            db.query(Transaction.id, Transaction.matched_with_id)
            .filter(
                Transaction.partner == "fino",
                Transaction.side == "bank",
                Transaction.recon_status == "matched",
            )
            .all()
        )

        total_matched_bank = len(matched_bank_rows)
        print(f"\n    Total bank rows with recon_status='matched': {total_matched_bank:,}")

        if total_matched_bank == 0:
            print("    [nothing to analyse — no matched bank rows]")
        else:
            # Collect the IDs they point to
            target_ids = [r.matched_with_id for r in matched_bank_rows if r.matched_with_id]
            null_targets = total_matched_bank - len(target_ids)

            # Batch-look-up the target rows
            if target_ids:
                target_rows = (
                    db.query(Transaction.id, Transaction.recon_status, Transaction.side)
                    .filter(Transaction.id.in_(target_ids))
                    .all()
                )
                target_map = {r.id: r for r in target_rows}
            else:
                target_map = {}

            count_dump_matched   = 0
            count_dump_unmatched = 0
            count_dump_other     = 0
            count_no_row         = 0

            for bank_row in matched_bank_rows:
                tid = bank_row.matched_with_id
                if tid is None:
                    count_no_row += 1
                    continue
                target = target_map.get(tid)
                if target is None:
                    count_no_row += 1
                elif target.recon_status == "matched":
                    count_dump_matched += 1
                elif target.recon_status == "unmatched":
                    count_dump_unmatched += 1
                else:
                    count_dump_other += 1

            subsection("Breakdown of what matched_with_id resolves to")
            fmt_row("matched_with_id IS NULL (no pointer at all)", f"{null_targets:,}")
            fmt_row("Points to a row with recon_status='matched'", f"{count_dump_matched:,}")
            fmt_row("Points to a row with recon_status='unmatched'", f"{count_dump_unmatched:,}")
            fmt_row("Points to a row with another status", f"{count_dump_other:,}")
            fmt_row("Points to an ID that does NOT exist in DB", f"{count_no_row - null_targets:,}")

        # ── 4. Sample 3 matched bank rows ────────────────────────────────────
        section("4. SAMPLE — 3 matched bank rows + dump row status they point to")

        sample_bank = (
            db.query(Transaction)
            .filter(
                Transaction.partner == "fino",
                Transaction.side == "bank",
                Transaction.recon_status == "matched",
            )
            .limit(3)
            .all()
        )

        if not sample_bank:
            print("    [no matched bank rows to sample]")
        else:
            for i, brow in enumerate(sample_bank, 1):
                print(f"\n    Sample {i}:")
                fmt_row("Bank row id", brow.id)
                fmt_row("Bank recon_status", brow.recon_status)
                fmt_row("Bank matched_with_id", str(brow.matched_with_id))
                fmt_row("Bank match_id", str(brow.match_id))
                fmt_row("Bank recon_date", str(brow.recon_date))

                if brow.matched_with_id:
                    dump_row = db.query(Transaction).filter(
                        Transaction.id == brow.matched_with_id
                    ).first()

                    if dump_row:
                        fmt_row("  -> Dump row id", dump_row.id)
                        fmt_row("  -> Dump side", str(dump_row.side))
                        fmt_row("  -> Dump partner", str(dump_row.partner))
                        fmt_row("  -> Dump recon_status", dump_row.recon_status)
                        fmt_row("  -> Dump match_id", str(dump_row.match_id))
                        fmt_row("  -> Dump recon_date", str(dump_row.recon_date))
                    else:
                        fmt_row("  -> Dump row", "[NOT FOUND — orphaned matched_with_id]")
                else:
                    fmt_row("  -> matched_with_id", "[NULL — no counterpart recorded]")

        # ── 5. recon_date distribution of dump rows ───────────────────────────
        section("5. DUMP ROW recon_date DISTRIBUTION — grouped by (recon_date, recon_status)")

        date_dist = (
            db.query(
                Transaction.recon_date,
                Transaction.recon_status,
                func.count(Transaction.id).label("cnt"),
            )
            .filter(Transaction.partner == "fino", Transaction.side == "internal")
            .group_by(Transaction.recon_date, Transaction.recon_status)
            .order_by(Transaction.recon_date, Transaction.recon_status)
            .all()
        )

        if not date_dist:
            print("    [no dump rows found]")
        else:
            print(f"\n    {'recon_date':<15} {'recon_status':<22} {'count':>8}")
            print(f"    {'-'*15} {'-'*22} {'-'*8}")
            for row in date_dist:
                print(f"    {str(row.recon_date):<15} {str(row.recon_status):<22} {row.cnt:>8,}")

        # ── Summary / hint ────────────────────────────────────────────────────
        section("DIAGNOSTIC SUMMARY")
        print("""
  What to look for:

  [Section 3] If "Points to a row with recon_status='unmatched'" > 0, the
    matching engine set bank.recon_status='matched' but never flipped the dump
    row to 'matched'.  That is the primary bug when bank shows 163 matched
    but dump shows 0.

  [Section 4] Check whether the dump row the bank points to really is 'unmatched'
    and whether its partner/side/recon_date look correct.

  [Section 5] If all dump rows land on recon_date=NULL (or a wrong date), the
    dashboard date filter may simply be hiding them — not a recon_status bug.
        """)

    finally:
        db.close()


if __name__ == "__main__":
    run_diagnostics()
