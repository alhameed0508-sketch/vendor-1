"""The write-behind decision log: non-approved decisions and analyst outcomes reach the database."""

from datetime import datetime, timedelta, timezone

from intelligence.decision_store import DecisionStore, PgDecisionSink
from intelligence.engine import UnifiedRiskEngine
from sqlalchemy import create_engine, select

from backend.infra.database.postgres import risk_decisions_table

IST = timezone(timedelta(hours=5, minutes=30))


def _engine():
    db = create_engine("sqlite://")
    risk_decisions_table.create(db)
    return db


def _pay(txn, payee, amount=5_000):
    return {
        "txn_id": txn,
        "from_account": "C1",
        "to_account": payee,
        "amount": amount,
        "timestamp": datetime(2026, 10, 1, 10, tzinfo=IST).isoformat(),
    }


def test_only_non_approved_decisions_and_outcomes_are_written():
    db = _engine()
    sink = PgDecisionSink(db, flush_seconds=0.01)
    risk = UnifiedRiskEngine(store=DecisionStore(sink=sink))
    risk.known_fraud.confirm("FRAUD-PAYEE", "test")
    held = risk.assess(_pay("T1", "FRAUD-PAYEE"), commit=True, source="ingest")
    approved = risk.assess(_pay("T2", "SHOP", 100), commit=True, source="ingest")
    risk.feedback(held.decision_id, "CONFIRMED_FRAUD", "checked", "analyst")
    sink.close()
    sink.write([held])  # flush anything the stopped thread left behind (idempotent update)
    with db.connect() as conn:
        rows = conn.execute(select(risk_decisions_table)).mappings().all()
    assert [r["decision_id"] for r in rows] == [held.decision_id]
    assert rows[0]["band"] == "REVIEW" and rows[0]["outcome"] == "CONFIRMED_FRAUD"
    assert rows[0]["reasons"][0]["code"] == "BI01"
    assert approved.band == "APPROVE"


def test_what_if_and_commit_with_the_same_txn_id_are_both_kept():
    db = _engine()
    sink = PgDecisionSink(db, flush_seconds=0.01)
    risk = UnifiedRiskEngine(store=DecisionStore(sink=sink))
    risk.known_fraud.confirm("FRAUD-PAYEE", "test")
    what_if = risk.assess(_pay("SAME", "FRAUD-PAYEE"), commit=False, source="api")
    real = risk.assess(_pay("SAME", "FRAUD-PAYEE"), commit=True, source="ingest")
    sink.close()
    sink.write([what_if, real])
    with db.connect() as conn:
        rows = conn.execute(select(risk_decisions_table.c.decision_id, risk_decisions_table.c.source)).all()
    assert {r.source for r in rows} == {"api", "ingest"} and len(rows) == 2


def test_a_database_failure_never_breaks_scoring():
    class Broken:
        def begin(self):
            raise RuntimeError("database down")

    sink = PgDecisionSink(Broken(), flush_seconds=0.01)
    risk = UnifiedRiskEngine(store=DecisionStore(sink=sink))
    risk.known_fraud.confirm("FRAUD-PAYEE", "test")
    assert risk.assess(_pay("T9", "FRAUD-PAYEE")).band == "REVIEW"
    sink.close()
