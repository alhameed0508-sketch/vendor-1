"""Verified-prevention figures: only investigator-confirmed alerts count as prevented."""

from services.kpi_service import KPIService


class _KpiRepo:
    def get(self):
        return {"fraud_prevented_inr": 900.0, "hours_saved": 0.0}


class _AlertRepo:
    def __init__(self, alerts):
        self._alerts = alerts

    def find_all(self, limit=50, **_):
        return self._alerts[:limit]


def _alert(status, amount):
    return {"status": status, "total_amount": amount}


def test_flagged_is_the_unverified_total_and_verified_counts_only_confirmed():
    alerts = [
        _alert("RESOLVED", 100.0),
        _alert("STR_FILED", 200.0),
        _alert("SUSPICION_CONFIRMED_ESCALATED", 300.0),
        _alert("FALSE_POSITIVE", 50.0),
        _alert("OPEN", 250.0),
    ]
    k = KPIService(_KpiRepo(), _AlertRepo(alerts)).get_kpis()
    assert k["fraud_flagged_inr"] == 900.0
    assert k["fraud_prevented_verified_inr"] == 600.0
    assert k["false_positive_inr"] == 50.0
    assert k["awaiting_review_inr"] == 250.0


def test_no_alerts_means_zero_verified():
    k = KPIService(_KpiRepo(), _AlertRepo([])).get_kpis()
    assert k["fraud_prevented_verified_inr"] == 0.0
    assert k["fraud_flagged_inr"] == 900.0
