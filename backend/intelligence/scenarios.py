"""Worked scenarios from the brief, replayed through the real engines.

Every scenario builds its own small, isolated engine (its own profiles, ring map and decision store), warms it
up with deterministic synthetic history, then scores the scenario's payment(s). Nothing here touches the live
or demo engines' state, and every decision is labelled ``source="scenario"``.

``expected_band`` is the design intent written before the run (what a careful bank should do), not a result.
The runner reports whether the engine's actual band matched it; a mismatch is shown, never hidden.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from intelligence.contracts import APPROVE, REVIEW, STEP_UP
from intelligence.decision_store import DecisionStore
from intelligence.engine import UnifiedRiskEngine
from intelligence.mule_network import MuleNetworkIntel
from intelligence.simulator import CITIES, IST, JourneySimulator

BASE = datetime(2026, 9, 1, tzinfo=IST)
HISTORY_DAYS = 45
SCENARIO_DAY = HISTORY_DAYS + 1


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    story: str
    expected_band: str
    why: str
    build: Callable[["_Builder"], List[Dict]]


class _Builder:
    """Deterministic history for the scenario's customers plus a background population with mule rings."""

    def __init__(self, seed: int = 11):
        self.rng = random.Random(seed)
        self.sim = JourneySimulator(seed=seed, customers=60, rings=2, start=BASE, run_tag="SC")
        self.history = [e.event for e in self.sim.run(days=HISTORY_DAYS, fraud_from_day=10_000)]
        self.n = 0

    def ring_mule(self) -> str:
        return self.sim.rings[0]["mules"][1]

    def txn(self) -> str:
        self.n += 1
        return f"SCN{self.n:06d}"

    def at(self, day: int, hour: int, minute: int = 0) -> datetime:
        return BASE + timedelta(days=day, hours=hour, minutes=minute)

    def session(
        self,
        customer: str,
        device: str,
        city: str = "Pune",
        when: Optional[datetime] = None,
        ip: Optional[str] = None,
        **extra,
    ) -> Dict:
        lat, lon = CITIES[city]
        sid = f"{customer}-{(when or BASE).strftime('%m%d%H%M')}"
        return {
            "session_id": sid,
            "device_id": device,
            "ip": ip or "10.20.30.40",
            "city": city,
            "lat": lat,
            "lon": lon,
            "auth_events": [],
            "typing_ms_per_char": extra.pop("typing", 210.0),
            **extra,
        }

    def payment(
        self,
        payer: str,
        payee: str,
        amount: float,
        when: datetime,
        session: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Dict:
        return {
            "txn_id": self.txn(),
            "from_account": payer,
            "to_account": payee,
            "amount": round(amount, 2),
            "timestamp": when.isoformat(),
            "session": session,
            "context": context or {"channel": "UPI_PUSH"},
        }

    def everyday_history(
        self,
        customer: str,
        device: str,
        typical: float,
        city: str = "Pune",
        hours=(9, 13, 19, 21),
        extra: Optional[Callable[[int], List[Dict]]] = None,
    ) -> None:
        """45 days of ordinary payments to a few merchants and contacts on the customer's own phone."""
        payees = [f"{customer}-MRC{k}" for k in range(6)] + [f"{customer}-FRIEND{k}" for k in range(3)]
        for day in range(HISTORY_DAYS):
            for _ in range(1 + (day % 3 == 0)):
                when = self.at(day, self.rng.choice(hours), self.rng.randint(0, 59))
                amount = math.exp(self.rng.gauss(math.log(typical), 0.45))
                self.history.append(
                    self.payment(
                        customer, self.rng.choice(payees), amount, when, self.session(customer, device, city, when)
                    )
                )
            if extra:
                self.history += extra(day)


def _customer_a_vs_b(b: _Builder) -> List[Dict]:
    def rent(day: int) -> List[Dict]:
        if day % 15 != 2:
            return []
        when = b.at(day, 10, 5)
        return [
            b.payment(
                "SC-CUST-A",
                "SC-LANDLORD-A",
                80_000 * b.rng.uniform(0.98, 1.02),
                when,
                b.session("SC-CUST-A", "SC-PHONE-A", "Pune", when),
            )
        ]

    b.everyday_history("SC-CUST-A", "SC-PHONE-A", 1_200, extra=rent)
    b.everyday_history("SC-CUST-B", "SC-PHONE-B", 450)
    when = b.at(SCENARIO_DAY, 10, 20)
    added = (when - timedelta(minutes=12)).isoformat()
    return [
        b.payment("SC-CUST-A", "SC-LANDLORD-A", 80_000, when, b.session("SC-CUST-A", "SC-PHONE-A", "Pune", when)),
        b.payment(
            "SC-CUST-B",
            "SC-NEWSELLER-B",
            80_000,
            when + timedelta(minutes=1),
            b.session("SC-CUST-B", "SC-PHONE-B", "Pune", when),
            {"channel": "UPI_PUSH", "beneficiary_added_at": added},
        ),
    ]


def _app_scam(b: _Builder) -> List[Dict]:
    b.everyday_history("SC-CUST-C", "SC-PHONE-C", 900)
    when = b.at(SCENARIO_DAY, 15, 40)
    return [
        b.payment(
            "SC-CUST-C",
            b.ring_mule(),
            85_000,
            when,
            b.session("SC-CUST-C", "SC-PHONE-C", "Pune", when),
            {
                "channel": "UPI_PUSH",
                "beneficiary_added_at": (when - timedelta(minutes=6)).isoformat(),
                "on_call": True,
                "note": "kyc update fee urgent",
                "app_switch_count": 6,
                "amount_pasted": True,
            },
        )
    ]


def _stolen_credentials_trusted_device(b: _Builder) -> List[Dict]:
    b.everyday_history("SC-CUST-D", "SC-PHONE-D", 700)
    when = b.at(SCENARIO_DAY, 2, 50)
    auth = [
        {"type": "sim_change", "at": (when - timedelta(minutes=25)).isoformat()},
        {"type": "password_reset", "at": (when - timedelta(minutes=14)).isoformat()},
    ]
    session = b.session("SC-CUST-D", "SC-PHONE-D", "Pune", when, auth_events=auth, remote_access=True, typing=95.0)
    added = (when - timedelta(minutes=4)).isoformat()
    return [
        b.payment(
            "SC-CUST-D",
            "SC-FRESH-PAYEE-D",
            49_500,
            when + timedelta(minutes=3 * k),
            dict(session),
            {"channel": "UPI_PUSH", "beneficiary_added_at": added},
        )
        for k in range(2)
    ]


def _genuine_traveller(b: _Builder) -> List[Dict]:
    b.everyday_history("SC-CUST-E", "SC-PHONE-E", 1_500)
    when = b.at(SCENARIO_DAY, 13, 10)
    return [
        b.payment("SC-CUST-E", "SC-CUST-E-MRC2", 2_400, when, b.session("SC-CUST-E", "SC-PHONE-E", "Kolkata", when))
    ]


def _festival_shopping(b: _Builder) -> List[Dict]:
    b.everyday_history("SC-CUST-F", "SC-PHONE-F", 800)
    when = b.at(SCENARIO_DAY, 19, 0)
    session = b.session("SC-CUST-F", "SC-PHONE-F", "Pune", when)
    return [
        b.payment("SC-CUST-F", f"SC-CUST-F-MRC{k % 6}", 2_600 + 300 * k, when + timedelta(minutes=8 * k), dict(session))
        for k in range(6)
    ]


SCENARIOS: Dict[str, Scenario] = {
    s.name: s
    for s in (
        Scenario(
            "customer_a_vs_b",
            "Same ₹80,000, two customers",
            "Customer A pays ₹80,000 rent to the same landlord every fortnight. Customer B usually spends about "
            "₹450 and suddenly sends ₹80,000 to a payee added 12 minutes ago, on their own phone.",
            STEP_UP,
            "A is approved (familiar payee, usual amount). B gets a step-up, not a hold: unusual and new, "
            "but no evidence of fraud.",
            _customer_a_vs_b,
        ),
        Scenario(
            "app_scam_mule_payee",
            "APP scam: ₹85,000 to a mule-ring account",
            "During a phone call the customer adds a payee 6 minutes before paying ₹85,000 with a 'KYC update' "
            "note. The payee is a member of a mule ring the network core already found.",
            REVIEW,
            "Held for review: the mule core places the payee in a ring and the intent engine sees a coached payment.",
            _app_scam,
        ),
        Scenario(
            "stolen_credentials_trusted_device",
            "Stolen credentials on the customer's own phone",
            "At 02:50 a SIM change and password reset are followed by a new payee and two ₹49,500 transfers. The "
            "phone is the customer's usual one, but a remote-access app is active and typing is twice as fast.",
            REVIEW,
            "Held for review: a takeover sequence plus remote access, even though the device is trusted.",
            _stolen_credentials_trusted_device,
        ),
        Scenario(
            "genuine_traveller",
            "Genuine customer on holiday",
            "A customer from Pune pays ₹2,400 at a shop they know, from Kolkata, on their usual phone.",
            APPROVE,
            "Approved: a new city alone is never a reason to interrupt.",
            _genuine_traveller,
        ),
        Scenario(
            "festival_shopping",
            "Festival shopping burst",
            "Six payments in under an hour to the customer's usual shops, larger than normal.",
            APPROVE,
            "Approved or at most a step-up: a burst to known shops is not fraud evidence.",
            _festival_shopping,
        ),
    )
}


def run_scenario(name: str, store: Optional[DecisionStore] = None, seed: int = 11) -> Dict:
    """Replay one scenario on an isolated engine. Decisions are also written to ``store`` when given."""
    scenario = SCENARIOS[name]
    builder = _Builder(seed)
    payments = scenario.build(builder)
    engine = UnifiedRiskEngine(mule=MuleNetworkIntel(builder.sim.accounts()), store=DecisionStore(max_decisions=500))
    builder.history.sort(key=lambda e: e["timestamp"])
    engine.warm_up(builder.history, builder.sim.accounts())
    decisions = []
    for payment in payments:
        decision = engine.assess(payment, commit=True, source="scenario", label=_label(name))
        if store is not None:
            store.put(decision)
        decisions.append(decision.to_dict(full=True))
    final = decisions[-1]["band"]
    if name == "customer_a_vs_b":
        matched = decisions[0]["band"] == APPROVE and final == STEP_UP
    elif name == "festival_shopping":
        matched = all(d["band"] in (APPROVE, STEP_UP) for d in decisions)
    else:
        matched = all(d["band"] == scenario.expected_band for d in decisions)
    return {
        "name": name,
        "title": scenario.title,
        "story": scenario.story,
        "expected_band": scenario.expected_band,
        "expected_why": scenario.why,
        "matched_expectation": matched,
        "decisions": decisions,
        "history_payments": len(builder.history),
        "data": "synthetic (scenario replay)",
    }


def _label(name: str) -> str:
    return "fraud" if name in ("app_scam_mule_payee", "stolen_credentials_trusted_device") else "genuine"


def list_scenarios() -> List[Dict]:
    return [
        {"name": s.name, "title": s.title, "story": s.story, "expected_band": s.expected_band, "expected_why": s.why}
        for s in SCENARIOS.values()
    ]
