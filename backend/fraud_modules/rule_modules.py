"""Rule-backed modules: each owns a subset of the existing rules and the rows it applies to.

A module never invents signals. It runs the shared RuleEngine on its own rows and says which of
its signals could not run because the data does not carry the field they need.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from detection.pipeline import RuleEngine

ACCOUNT, TRANSACTION = "account", "transaction"


@dataclass(frozen=True)
class Finding:
    module_id: str
    account_id: str
    rule_code: str
    explanation: str


@dataclass(frozen=True)
class SkippedSignal:
    rule_code: str
    reason: str


@dataclass(frozen=True)
class ModuleRun:
    module_id: str
    findings: Tuple[Finding, ...]
    signals_run: Tuple[str, ...]
    signals_skipped: Tuple[SkippedSignal, ...]
    rows_considered: int


@dataclass(frozen=True)
class RuleModule:
    module_id: str
    rule_codes: Tuple[str, ...]
    channel: Optional[str] = None
    # rule code -> (where the field lives, field name); a rule listed here needs that field populated
    requires: Tuple[Tuple[str, str, str], ...] = ()

    def run(self, accounts, transactions) -> ModuleRun:
        rows = tuple(t for t in transactions if self.channel is None or t.get("channel") == self.channel)
        in_scope = {r for t in rows for r in (t["from_account"], t["to_account"])}
        accts = tuple(a for a in accounts if self.channel is None or a["account_id"] in in_scope)

        skipped = tuple(
            SkippedSignal(code, f"no {where} in this data carries '{field}'")
            for code, where, field in self.requires
            if not any(r.get(field) for r in (accts if where == ACCOUNT else rows))
        )
        blocked = {s.rule_code for s in skipped}
        runnable = frozenset(c for c in self.rule_codes if c not in blocked)

        hits: Dict[str, list] = RuleEngine().evaluate(accts, rows, rule_codes=runnable) if runnable else {}
        findings = tuple(
            Finding(self.module_id, account_id, hit.split(":", 1)[0], hit)
            for account_id, account_hits in hits.items()
            for hit in account_hits
        )
        return ModuleRun(
            self.module_id,
            findings,
            tuple(c for c in self.rule_codes if c in runnable),
            skipped,
            len(rows),
        )


UPI = RuleModule(
    "upi",
    ("R14", "R15", "R17", "R18"),
    channel="UPI",
    requires=(("R15", ACCOUNT, "upi_id"), ("R18", TRANSACTION, "device_id")),
)

TRANSACTION_AML = RuleModule("transaction_aml", ("R06", "R12", "R14"))

# Duplicate-identity matching works on onboarding applications, not on the account dataset, so it
# stays behind /onboarding. Only the early-life signal can be read from accounts and transactions.
IDENTITY = RuleModule("identity", ("R20",), requires=(("R20", ACCOUNT, "account_age_days"),))

RULE_MODULES = {m.module_id: m for m in (UPI, TRANSACTION_AML, IDENTITY)}
