"""
An auto-closed refund CREDIT is NOT netted automatically — that is deliberate.

DO NOT "FIX" THIS. I started to, on 2026-09-04, and it was wrong. Recording why.

The shape looks like a bug. A bank refund round trip arrives as:

    bank DR  IMPS/P2A/<tracking>/<name>/...   -> txn / unmatched                (sits open)
    bank CR  IMPS/P2A/<tracking>/<acct>/...   -> settlement_credit / fund_transfer

The credit is really the reversal of that debit, but a bare credit is auto-closed at ingest as
an inbound settlement, so run_bank_reversal_match — which filters candidates on
recon_status == 'unmatched' — never sees it and the debit stays open. Its docstring even says
row_type is ignored "on purpose: a refund credit is often classified 'settlement_credit'…",
which reads like the status filter is an oversight contradicting the stated intent.

It is not. The intended flow is HUMAN-IN-THE-LOOP:

    Open Items -> select the Fund-Transfer row -> "Remove from Fund Transfer"
      (routes/recon.py::do_remove_fund_transfer, and a bulk variant)
      -> the row reopens to 'unmatched'
      -> run_bank_reversal_match then nets the round trip immediately

That action was built for finance-ops in 2026-08 for exactly this shape, and
test_bank_reversal_match.py::test_remove_fund_transfer_reopens_and_nets asserts the pass
returns 0 BEFORE the operator acts. The docstring's "row_type is ignored" applies AFTER the
reopen: the row is then 'unmatched' but still carries row_type 'settlement_credit', and
ignoring row_type is what lets it net.

Deciding that an auto-closed credit is a refund rather than a genuine settlement inflow is a
money call, so a person makes it. Widening the candidate query to admit auto-closed credits
would have silently netted ~518 pairs (~Rs 53.5 lakh of debits) across production and removed
that control for every future row.

If the manual step is ever judged too slow, that is a POLICY decision to be signed off — not a
quiet change to the matching engine — and the bulk "Remove from Fund Transfer" button already
exists for clearing a backlog.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Base, Transaction, ReconStatus, generate_id
from core.matching_engine import run_bank_reversal_match

P, D = "axis", "2026-09-03"
TRK = "624615717386"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    # Guard A needs an internal row for the date; internal_matched so Guard B does not hold
    # the tracking back.
    s.add(Transaction(id=generate_id(), partner=P, side="internal", row_type="txn",
                      recon_date=D, recon_status=ReconStatus.internal_matched,
                      amount=5000.0, dr_cr="DR", tracking_number=TRK))
    s.commit()
    yield s
    s.close()


def _bank(db, dr_cr, amount, status, row_type, trk=TRK):
    t = Transaction(id=generate_id(), partner=P, side="bank", row_type=row_type,
                    recon_date=D, recon_status=status, amount=amount, dr_cr=dr_cr,
                    tracking_number=trk, bank_description=f"IMPS/P2A/{trk}/x/y")
    db.add(t); db.commit()
    return t


def test_autoclosed_credit_is_not_netted_automatically(db):
    """The control: the pass must leave the pair alone until a human reopens the credit."""
    dr = _bank(db, "DR", 5000.0, ReconStatus.unmatched, "txn")
    cr = _bank(db, "CR", 5000.0, ReconStatus.fund_transfer, "settlement_credit")
    assert run_bank_reversal_match(P, D, db, None)["bank_reversal_matched"] == 0
    db.refresh(dr); db.refresh(cr)
    assert dr.recon_status == ReconStatus.unmatched
    assert cr.recon_status == ReconStatus.fund_transfer


def test_the_operator_action_is_what_unlocks_it(db):
    """Remove from Fund Transfer reopens the credit and the round trip nets at once."""
    from models.database import User
    from routes.recon import do_remove_fund_transfer, RemoveFundTransferRequest
    dr = _bank(db, "DR", 5000.0, ReconStatus.unmatched, "txn")
    cr = _bank(db, "CR", 5000.0, ReconStatus.fund_transfer, "settlement_credit")
    user = User(id="u1", username="raj", role="admin", permissions="{}")

    out = do_remove_fund_transfer(RemoveFundTransferRequest(transaction_id=cr.id),
                                  db=db, current_user=user)
    assert out["matched"] is True
    db.refresh(dr); db.refresh(cr)
    assert dr.recon_status == ReconStatus.reversal_matched
    assert cr.recon_status == ReconStatus.reversal_matched
    assert dr.match_id and dr.match_id == cr.match_id


def test_once_reopened_row_type_is_ignored(db):
    """What the docstring's "row_type is ignored" actually refers to: after the reopen the row
    is 'unmatched' but still row_type 'settlement_credit', and it must still net."""
    dr = _bank(db, "DR", 5000.0, ReconStatus.unmatched, "txn")
    cr = _bank(db, "CR", 5000.0, ReconStatus.unmatched, "settlement_credit")
    assert run_bank_reversal_match(P, D, db, None)["bank_reversal_matched"] == 1
    db.refresh(dr); db.refresh(cr)
    assert dr.recon_status == cr.recon_status == ReconStatus.reversal_matched
