"""Labelled synthetic customer journeys (SIMULATED DATA - every event says so).

The team has no bank data, so the unified engine is demonstrated and evaluated on a simulator that
produces what a bank's switch would send: payments with session context (device, IP, place, login
events, typing rhythm) and payment context (note, call, channel, payee added time).

Genuine customers have homes, devices, merchants, contacts and monthly payees. Fraud is injected as:
  - APP scams: a customer is talked into paying a mule account they just added;
  - account takeovers: credential/SIM change -> login from elsewhere -> payee added -> transfers,
    including stolen credentials on the customer's own device (the brief's scenario);
  - mule activity: mules forwarding victims' money to an aggregator within hours.
Genuine-but-unusual cases are injected on purpose (the false-positive traps): big monthly payments to a
known payee, travel, phone upgrades, festival sprees, genuine password resets, large first payments.

Labels ("fraud" / "genuine") travel next to each event and are never passed to the engine for scoring.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional, Tuple

CITIES = {
    "Mumbai": (19.076, 72.877),
    "Delhi": (28.704, 77.102),
    "Bengaluru": (12.972, 77.594),
    "Chennai": (13.083, 80.270),
    "Hyderabad": (17.385, 78.487),
    "Kolkata": (22.573, 88.364),
    "Pune": (18.520, 73.857),
    "Ahmedabad": (23.023, 72.571),
    "Jaipur": (26.912, 75.787),
    "Lucknow": (26.847, 80.947),
    "Kochi": (9.931, 76.267),
    "Coimbatore": (11.017, 76.956),
}
# Synthetic "bad" IPs used by fraudsters in the simulator. The evaluation loads them as a test feed;
# the live app uses the real Tor and Spamhaus lists instead.
SIM_BAD_IPS = tuple(f"203.0.113.{i}" for i in range(10, 40))
SCAM_NOTES = (
    "kyc update fee",
    "refund process charge",
    "digital arrest settlement",
    "customs duty courier seized",
    "task reward deposit",
    "electricity bill pending",
)
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class SimCustomer:
    cid: str
    city: str
    devices: List[str]
    ip_prefix: str
    typing_ms: float
    hours: List[int]
    merchants: List[str]
    contacts: List[str]
    big_payee: Optional[str]
    big_amount: float
    mu: float  # log-amount centre for everyday spending
    rate: float  # payments per day
    session_n: int = 0
    added: Dict[str, float] = field(default_factory=dict)


@dataclass
class SimEvent:
    event: Dict
    label: str  # "fraud" | "genuine"
    kind: str  # e.g. "everyday", "app_scam", "ato", "mule_forward", "trap_big_known_payee", ...


class JourneySimulator:
    def __init__(
        self,
        seed: int = 7,
        customers: int = 400,
        rings: int = 4,
        mules_per_ring: int = 6,
        start: Optional[datetime] = None,
        run_tag: str = "S",
    ):
        self.rng = random.Random(seed)
        self.start = start or datetime(2026, 9, 1, tzinfo=IST)
        self.tag = run_tag
        self.n = 0
        self.customers = [self._customer(i) for i in range(customers)]
        self.rings = []
        for r in range(rings):
            members = [f"{self.tag}MULE{r:02d}_{m:02d}" for m in range(mules_per_ring)]
            self.rings.append(
                {"collector": members[0], "mules": members[1:-1], "aggregator": members[-1], "members": members}
            )
        self.mule_accounts = [m for ring in self.rings for m in ring["members"]]
        self.fresh_mules: List[str] = []  # brand-new mule accounts created during APP scams / takeovers

    # ------------------------------------------------------------------ people
    def _customer(self, i: int) -> SimCustomer:
        rng = self.rng
        city = rng.choice(list(CITIES))
        devices = [f"{self.tag}DEV{i:04d}A"] + ([f"{self.tag}DEV{i:04d}B"] if rng.random() < 0.3 else [])
        peak = rng.choice([(8, 9, 13, 19, 20, 21), (10, 12, 14, 18, 19), (7, 8, 12, 13, 20, 22), (9, 11, 17, 21, 23)])
        big = rng.random() < 0.35
        return SimCustomer(
            cid=f"{self.tag}CUST{i:04d}",
            city=city,
            devices=devices,
            ip_prefix=f"10.{i // 250}.{i % 250}",
            typing_ms=rng.uniform(140, 320),
            hours=list(peak),
            merchants=[f"MRC{rng.randint(1, 900):04d}" for _ in range(rng.randint(5, 12))],
            contacts=[f"{self.tag}CUST{rng.randint(0, 9999):04d}X" for _ in range(rng.randint(2, 5))],
            big_payee=f"{self.tag}LANDLORD{i:04d}" if big else None,
            big_amount=rng.uniform(25_000, 95_000),
            mu=math.log(rng.uniform(250, 1800)),
            rate=rng.uniform(0.6, 2.2),
        )

    # ----------------------------------------------------------------- helpers
    def _txn(self) -> str:
        self.n += 1
        return f"{self.tag}T{self.n:08d}"

    def _ts(self, day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
        return self.start + timedelta(days=day, hours=hour, minutes=minute, seconds=second)

    def _session(
        self,
        c: SimCustomer,
        when: datetime,
        device: Optional[str] = None,
        city: Optional[str] = None,
        ip: Optional[str] = None,
        auth_events=(),
        new_session: bool = True,
        **extra,
    ) -> Dict:
        if new_session:
            c.session_n += 1
        city = city or c.city
        lat, lon = CITIES[city]
        return {
            "session_id": f"{c.cid}-S{c.session_n}",
            "device_id": device or c.devices[0],
            "ip": ip or f"{c.ip_prefix}.{self.rng.randint(2, 250)}",
            "city": city,
            "lat": round(lat + self.rng.uniform(-0.05, 0.05), 4),
            "lon": round(lon + self.rng.uniform(-0.05, 0.05), 4),
            "auth_events": list(auth_events),
            "typing_ms_per_char": round(c.typing_ms * self.rng.uniform(0.9, 1.1), 1),
            **extra,
        }

    def _event(
        self,
        payer: str,
        payee: str,
        amount: float,
        when: datetime,
        session: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Dict:
        return {
            "txn_id": self._txn(),
            "from_account": payer,
            "to_account": payee,
            "amount": round(amount, 2),
            "timestamp": when.isoformat(),
            "session": session,
            "context": context or {"channel": "UPI_PUSH"},
        }

    # ------------------------------------------------------------- generators
    def everyday(self, c: SimCustomer, day: int) -> List[SimEvent]:
        rng, out = self.rng, []
        for _ in range(self._poisson(c.rate)):
            hour = rng.choice(c.hours)
            when = self._ts(day, hour, rng.randint(0, 59), rng.randint(0, 59))
            roll = rng.random()
            if roll < 0.62:
                payee, amount = rng.choice(c.merchants), math.exp(rng.gauss(c.mu, 0.6))
            else:
                payee, amount = rng.choice(c.contacts), math.exp(rng.gauss(c.mu + 0.7, 0.6))
            device = c.devices[0] if rng.random() < 0.93 or len(c.devices) == 1 else c.devices[1]
            out.append(
                SimEvent(
                    self._event(c.cid, payee, amount, when, self._session(c, when, device=device)),
                    "genuine",
                    "everyday",
                )
            )
        if c.big_payee and day % 15 == 3:  # fortnightly instalment (rent, fees, SIP)
            when = self._ts(day, 10, rng.randint(0, 59))
            out.append(
                SimEvent(
                    self._event(
                        c.cid, c.big_payee, c.big_amount * rng.uniform(0.95, 1.05), when, self._session(c, when)
                    ),
                    "genuine",
                    "instalment_big_payee",
                )
            )
        return out

    def _poisson(self, lam: float) -> int:
        k, p, limit = 0, 1.0, math.exp(-lam)
        while True:
            p *= self.rng.random()
            if p <= limit:
                return k
            k += 1

    def app_scam(
        self, c: SimCustomer, day: int, amount: Optional[float] = None, quiet: bool = False, fresh_mule: bool = False
    ) -> List[SimEvent]:
        """Authorised push-payment scam: the customer adds a mule payee during a call and pays.

        ``quiet``: no call, scam note or coaching signals reach the bank (the hard, common case).
        ``fresh_mule``: the payee is a brand-new account never seen before (no network history at all).
        """
        rng = self.rng
        ring = rng.choice(self.rings)
        mule = self._fresh_mule() if fresh_mule else rng.choice(ring["mules"])
        when = self._ts(day, rng.choice([11, 15, 18, 20]), rng.randint(0, 50))
        added = when - timedelta(minutes=rng.randint(3, 15))
        if quiet or fresh_mule:
            context = {"channel": "UPI_PUSH", "beneficiary_added_at": added.isoformat()}
        else:
            context = {
                "channel": "UPI_PUSH",
                "beneficiary_added_at": added.isoformat(),
                "on_call": rng.random() < 0.75,
                "note": rng.choice(SCAM_NOTES) if rng.random() < 0.5 else "",
                "app_switch_count": rng.randint(4, 9) if rng.random() < 0.5 else 0,
                "amount_pasted": rng.random() < 0.4,
            }
        amt = amount or rng.choice([25_000, 49_500, 85_000, 1_20_000]) * rng.uniform(0.9, 1.1)
        kind = "app_scam_fresh_mule" if fresh_mule else "app_scam_quiet" if quiet else "app_scam"
        out = [SimEvent(self._event(c.cid, mule, amt, when, self._session(c, when), context), "fraud", kind)]
        out += self.mule_forward(ring, mule, amt, when)
        return out

    def _fresh_mule(self) -> str:
        account = f"{self.tag}NEWMULE{self._txn()[len(self.tag) + 1 :]}"
        self.fresh_mules.append(account)
        return account

    def quiet_takeover(self, c: SimCustomer, day: int) -> List[SimEvent]:
        """Stolen credentials used carefully: residential IP in the victim's own city, no reset, a new phone."""
        rng = self.rng
        ring = rng.choice(self.rings)
        fresh = rng.random() < 0.5
        mule = self._fresh_mule() if fresh else rng.choice(ring["mules"])
        when = self._ts(day, rng.choice(c.hours), rng.randint(0, 40))
        device = f"{self.tag}ATQ{rng.randint(1, 500):03d}"
        session = self._session(
            c, when, device=device, ip=f"49.{rng.randint(32, 63)}.{rng.randint(0, 255)}.{rng.randint(2, 250)}"
        )
        ctx = {
            "channel": "UPI_PUSH",
            "beneficiary_added_at": (when - timedelta(minutes=rng.randint(30, 300))).isoformat(),
        }
        out = [
            SimEvent(self._event(c.cid, mule, rng.uniform(15_000, 60_000), when, session, ctx), "fraud", "ato_quiet")
        ]
        out += self.mule_forward(ring, mule, 40_000, when)
        return out

    def mule_forward(self, ring: Dict, mule: str, amount: float, when: datetime) -> List[SimEvent]:
        """The mule passes the money on within hours (that is the mule core's territory)."""
        rng, out = self.rng, []
        t = when + timedelta(minutes=rng.randint(20, 150))
        left = amount * rng.uniform(0.92, 0.98)
        parts = rng.randint(1, 3)
        for k in range(parts):
            share = left / parts
            target = ring["aggregator"] if rng.random() < 0.7 else rng.choice([m for m in ring["mules"] if m != mule])
            out.append(
                SimEvent(
                    self._event(mule, target, share, t + timedelta(minutes=7 * k), self._mule_session(ring, mule, k)),
                    "fraud",
                    "mule_forward",
                )
            )
        return out

    def mule_seed(self, day: int) -> List[SimEvent]:
        """Background ring activity: many victims pay each mule, who forwards nearly all of it within hours."""
        rng, out = self.rng, []
        for r, ring in enumerate(self.rings):
            for m, mule in enumerate(ring["mules"]):
                when = self._ts(day, rng.randint(9, 19), rng.randint(0, 59))
                received = 0.0
                for v in range(rng.randint(3, 5)):
                    amt = rng.uniform(8_000, 45_000)
                    received += amt
                    victim = f"{self.tag}EXTV{day:02d}{r}{m}{v}{rng.randint(0, 99):02d}"
                    out.append(
                        SimEvent(
                            self._event(victim, mule, amt, when + timedelta(minutes=11 * v)), "fraud", "mule_inbound"
                        )
                    )
                out += self.mule_forward(ring, mule, received, when + timedelta(minutes=50))
            if day % 2 == 0:
                when = self._ts(day, rng.randint(9, 22), rng.randint(0, 59))
                for mule in ring["mules"]:
                    out.append(
                        SimEvent(
                            self._event(
                                ring["collector"],
                                mule,
                                rng.uniform(42_000, 49_800),
                                when,
                                self._mule_session(ring, mule),
                            ),
                            "fraud",
                            "mule_forward",
                        )
                    )
                    when += timedelta(minutes=rng.randint(2, 6))
        return out

    def _mule_session(self, ring: Dict, account: str, k: int = 0) -> Dict:
        return {
            "session_id": f"{account}-S{k}",
            "device_id": f"{ring['collector']}-PHONE",
            "ip": self.rng.choice(SIM_BAD_IPS),
            "city": "Kolkata",
            "lat": 22.57,
            "lon": 88.36,
            "auth_events": [],
        }

    def account_takeover(self, c: SimCustomer, day: int, own_device: bool = False) -> List[SimEvent]:
        """Stolen credentials: change -> login elsewhere -> payee added -> quick transfers."""
        rng = self.rng
        ring = rng.choice(self.rings)
        mule = rng.choice(ring["mules"])
        when = self._ts(day, rng.choice([1, 2, 3, 23]), rng.randint(0, 40))
        far = rng.choice([x for x in CITIES if x != c.city])
        auth = [
            {
                "type": rng.choice(["password_reset", "sim_change", "mpin_reset"]),
                "at": (when - timedelta(minutes=rng.randint(5, 20))).isoformat(),
            }
        ]
        device = c.devices[0] if own_device else f"{self.tag}ATK{rng.randint(1, 50):03d}"
        ip = rng.choice(SIM_BAD_IPS) if rng.random() < 0.6 else f"100.{rng.randint(64, 127)}.{rng.randint(0, 255)}.9"
        added = when - timedelta(minutes=rng.randint(2, 8))
        session = self._session(
            c, when, device=device, city=far, ip=ip, auth_events=auth, remote_access=own_device and rng.random() < 0.5
        )
        session["typing_ms_per_char"] = round(c.typing_ms * rng.choice([0.45, 1.9]), 1)
        out = []
        for k in range(rng.randint(2, 4)):
            t = when + timedelta(minutes=3 * k)
            ctx = {"channel": "UPI_PUSH", "beneficiary_added_at": added.isoformat()}
            out.append(
                SimEvent(
                    self._event(c.cid, mule, rng.uniform(30_000, 95_000), t, dict(session, auth_events=auth), ctx),
                    "fraud",
                    "ato_own_device" if own_device else "ato",
                )
            )
        out += self.mule_forward(ring, mule, 60_000, when)
        return out

    def traps(self, c: SimCustomer, day: int) -> List[SimEvent]:
        """Genuine but unusual: the payments a naive system flags."""
        rng = self.rng
        kind = rng.choice(
            ["travel", "new_phone", "festival", "new_payee_large", "night", "password_reset", "big_known_payee"]
        )
        when = self._ts(day, rng.choice(c.hours), rng.randint(0, 50))
        if kind == "travel":
            city = rng.choice([x for x in CITIES if x != c.city])
            return [
                SimEvent(
                    self._event(
                        c.cid,
                        f"MRC{rng.randint(1, 900):04d}",
                        math.exp(c.mu + 0.8),
                        when + timedelta(days=1),
                        self._session(c, when + timedelta(days=1), city=city),
                    ),
                    "genuine",
                    "trap_travel",
                )
            ]
        if kind == "new_phone":
            c.devices.insert(0, f"{self.tag}NEW{c.cid[-4:]}{day}")
            return [
                SimEvent(
                    self._event(c.cid, rng.choice(c.contacts), math.exp(c.mu + 0.5), when, self._session(c, when)),
                    "genuine",
                    "trap_new_phone",
                )
            ]
        if kind == "festival":
            return [
                SimEvent(
                    self._event(
                        c.cid,
                        f"MRC{rng.randint(1, 900):04d}",
                        math.exp(rng.gauss(c.mu + 0.9, 0.4)),
                        when + timedelta(minutes=9 * k),
                        self._session(c, when, new_session=k == 0),
                    ),
                    "genuine",
                    "trap_festival",
                )
                for k in range(rng.randint(5, 7))
            ]
        if kind == "new_payee_large":
            payee = f"{self.tag}SELLER{rng.randint(1, 9999):04d}"
            ctx = {"channel": "UPI_PUSH", "beneficiary_added_at": (when - timedelta(minutes=20)).isoformat()}
            return [
                SimEvent(
                    self._event(c.cid, payee, rng.uniform(30_000, 70_000), when, self._session(c, when), ctx),
                    "genuine",
                    "trap_new_payee_large",
                )
            ]
        if kind == "night":
            t = self._ts(day, 3, rng.randint(0, 50))
            return [
                SimEvent(
                    self._event(c.cid, rng.choice(c.merchants), math.exp(c.mu), t, self._session(c, t)),
                    "genuine",
                    "trap_night",
                )
            ]
        if kind == "password_reset":
            auth = [{"type": "password_reset", "at": (when - timedelta(minutes=10)).isoformat()}]
            return [
                SimEvent(
                    self._event(
                        c.cid,
                        rng.choice(c.contacts),
                        math.exp(c.mu + 0.6),
                        when,
                        self._session(c, when, auth_events=auth),
                    ),
                    "genuine",
                    "trap_password_reset",
                )
            ]
        payee = c.big_payee or rng.choice(c.contacts)
        amt = (c.big_amount if c.big_payee else math.exp(c.mu + 1.2)) * rng.uniform(1.2, 1.6)
        return [
            SimEvent(self._event(c.cid, payee, amt, when, self._session(c, when)), "genuine", "trap_big_known_payee")
        ]

    # --------------------------------------------------------------- the story
    def run(
        self, days: int = 60, fraud_from_day: int = 45, fraud_per_day: float = 6.0, traps_per_day: float = 12.0
    ) -> List[SimEvent]:
        """All events in time order. Fraud and traps start at ``fraud_from_day`` (after the warm-up)."""
        events: List[SimEvent] = []
        for day in range(days):
            for c in self.customers:
                events += self.everyday(c, day)
            events += self.mule_seed(day)
            if day >= fraud_from_day:
                for _ in range(self._poisson(fraud_per_day)):
                    c = self.rng.choice(self.customers)
                    roll = self.rng.random()
                    if roll < 0.35:
                        events += self.app_scam(c, day)
                    elif roll < 0.50:
                        events += self.app_scam(c, day, quiet=True)
                    elif roll < 0.62:
                        events += self.app_scam(c, day, fresh_mule=True)
                    elif roll < 0.80:
                        events += self.account_takeover(c, day)
                    elif roll < 0.90:
                        events += self.account_takeover(c, day, own_device=True)
                    else:
                        events += self.quiet_takeover(c, day)
                for _ in range(self._poisson(traps_per_day)):
                    events += self.traps(self.rng.choice(self.customers), day)
        events.sort(key=lambda e: e.event["timestamp"])
        return events

    def accounts(self) -> List[Dict]:
        """Account stubs for the mule core (mules are young accounts; no labels here)."""
        out = [{"account_id": c.cid, "account_age_days": 900} for c in self.customers]
        out += [{"account_id": m, "account_age_days": 12} for m in self.mule_accounts]
        return out


def day_of(event: Dict, start: datetime) -> int:
    return (datetime.fromisoformat(event["timestamp"]) - start).days


def split_by_day(events: List[SimEvent], start: datetime, cut: int) -> Tuple[List[SimEvent], List[SimEvent]]:
    before = [e for e in events if day_of(e.event, start) < cut]
    return before, [e for e in events if day_of(e.event, start) >= cut]


def stream(events: List[SimEvent]) -> Iterator[SimEvent]:
    yield from events
