"""Gather every module's findings for the loaded dataset in one list of Finding records."""

from typing import Dict, List

from fraud_modules.rule_modules import RULE_MODULES, Finding


def mule_findings(alerts: List[Dict]) -> List[Finding]:
    """One finding per account in each mule alert, carrying the alert's own risk score."""
    return [
        Finding(
            "mule",
            node["account_id"],
            "ALERT",
            f"{alert['alert_id']}: {alert.get('explanation') or 'mule cluster alert'}",
            score=alert.get("risk_score"),
        )
        for alert in alerts
        for node in alert.get("nodes", [])
    ]


def collect_findings(alerts: List[Dict], dataset: Dict) -> List[Finding]:
    accounts, transactions = dataset.get("accounts", []), dataset.get("transactions", [])
    rule_findings = [f for m in RULE_MODULES.values() for f in m.run(accounts, transactions).findings]
    return mule_findings(alerts) + rule_findings
