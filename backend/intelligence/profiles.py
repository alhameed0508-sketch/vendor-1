"""Per-customer behaviour profiles and per-payee intelligence, kept in memory and bounded.

Everything uses the event's own timestamp (never the wall clock), so replayed or late events are
judged by when they happened. Profiles are derived data: they can be rebuilt from committed events.
"""

from __future__ import annotations

import math
import statistics
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, Optional, Set, Tuple

MAX_AMOUNTS = 200
MAX_EVENT_TIMES = 500
MAX_INBOUND = 500
DAY_S = 86400.0
HOUR_S = 3600.0


def event_seconds(timestamp) -> float:
    """ISO-8601 string or datetime -> POSIX seconds. Naive times are taken as UTC."""
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    if isinstance(timestamp, datetime):
        dt = timestamp
    else:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def local_hour(seconds: float) -> int:
    """Hour of day in India (UTC+5:30), which is how customers' habits are recorded."""
    return int(((seconds + 5.5 * HOUR_S) % DAY_S) // HOUR_S)


@dataclass
class PayeeHistory:
    count: int = 0
    log_sum: float = 0.0
    first_paid: float = 0.0
    last_paid: float = 0.0

    @property
    def usual_amount(self) -> float:
        return math.exp(self.log_sum / self.count) if self.count else 0.0


@dataclass
class CustomerProfile:
    customer_id: str
    first_seen: float = 0.0
    last_seen: float = 0.0
    n_payments: int = 0
    log_amounts: Deque[float] = field(default_factory=lambda: deque(maxlen=MAX_AMOUNTS))
    event_times: Deque[float] = field(default_factory=lambda: deque(maxlen=MAX_EVENT_TIMES))
    hours: list = field(default_factory=lambda: [0] * 24)
    payees: Dict[str, PayeeHistory] = field(default_factory=dict)
    devices: Dict[str, float] = field(default_factory=dict)  # device -> first seen
    places: Dict[str, int] = field(default_factory=dict)
    typing_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    last_session: Optional[Dict] = None
    trusted_payees: Set[str] = field(default_factory=set)
    trusted_devices: Set[str] = field(default_factory=set)
    trusted_places: Set[str] = field(default_factory=set)

    # ---------------------------------------------------------------- reads
    @property
    def history_days(self) -> float:
        return max(0.0, (self.last_seen - self.first_seen) / DAY_S) if self.n_payments else 0.0

    def confidence(self) -> float:
        """How much the baseline can be trusted: grows with payments and days of history."""
        return round(min(1.0, self.n_payments / 30.0) * min(1.0, self.history_days / 14.0), 3)

    def amount_stats(self) -> Tuple[float, float, float]:
        """(median log-amount, robust spread, 99th-percentile amount) of the customer's history."""
        logs = list(self.log_amounts)
        if len(logs) < 3:
            return 0.0, 0.0, 0.0
        med = statistics.median(logs)
        mad = statistics.median(abs(x - med) for x in logs) * 1.4826
        spread = max(mad, 0.25)  # never treat a perfectly regular customer as infinitely certain
        ordered = sorted(logs)
        p99 = math.exp(ordered[min(len(ordered) - 1, int(0.99 * (len(ordered) - 1)))])
        return med, spread, p99

    def hour_share(self, hour: int) -> float:
        total = sum(self.hours)
        return self.hours[hour] / total if total else 0.0

    def payments_in_window(self, at: float, seconds: float) -> int:
        return sum(1 for t in self.event_times if at - seconds < t <= at)

    def usual_busiest_hour(self, before: float) -> int:
        """Most payments this customer made in any one-hour span before ``before``."""
        times = sorted(t for t in self.event_times if t <= before - HOUR_S)
        best, j = 0, 0
        for i, t in enumerate(times):
            while times[j] < t - HOUR_S:
                j += 1
            best = max(best, i - j + 1)
        return best

    # --------------------------------------------------------------- writes
    def commit(
        self,
        payee: str,
        amount: float,
        at: float,
        device: str = "",
        place: str = "",
        session: Optional[Dict] = None,
        typing_ms: Optional[float] = None,
    ) -> None:
        if not self.n_payments:
            self.first_seen = at
        self.first_seen = min(self.first_seen, at)
        self.last_seen = max(self.last_seen, at)
        self.n_payments += 1
        self.log_amounts.append(math.log(max(amount, 1.0)))
        self.event_times.append(at)
        self.hours[local_hour(at)] += 1
        hist = self.payees.setdefault(payee, PayeeHistory(first_paid=at))
        hist.count += 1
        hist.log_sum += math.log(max(amount, 1.0))
        hist.last_paid = max(hist.last_paid, at)
        if device:
            self.devices.setdefault(device, at)
        if place:
            self.places[place] = self.places.get(place, 0) + 1
        if typing_ms:
            self.typing_ms.append(float(typing_ms))
        if session:
            self.last_session = {**session, "at": at}


@dataclass
class PayeeIntel:
    account_id: str
    first_seen: float = 0.0
    inbound: Deque[Tuple[float, str]] = field(default_factory=lambda: deque(maxlen=MAX_INBOUND))
    first_payment_by: Dict[str, float] = field(default_factory=dict)
    inbound_total: float = 0.0
    outbound_total: float = 0.0

    def new_payers(self, at: float, seconds: float = DAY_S) -> int:
        return sum(1 for t in self.first_payment_by.values() if at - seconds < t <= at)

    def age_days(self, at: float) -> float:
        return (at - self.first_seen) / DAY_S if self.first_seen else 0.0


class ProfileStore:
    """Bounded LRU stores for customer profiles and payee intelligence."""

    def __init__(self, max_customers: int = 200_000, max_payees: int = 400_000):
        self._customers: "OrderedDict[str, CustomerProfile]" = OrderedDict()
        self._payees: "OrderedDict[str, PayeeIntel]" = OrderedDict()
        self._max_customers = max_customers
        self._max_payees = max_payees

    def customer(self, customer_id: str, create: bool = False) -> Optional[CustomerProfile]:
        prof = self._customers.get(customer_id)
        if prof is not None:
            self._customers.move_to_end(customer_id)
        elif create:
            prof = self._customers[customer_id] = CustomerProfile(customer_id)
            while len(self._customers) > self._max_customers:
                self._customers.popitem(last=False)
        return prof

    def payee(self, account_id: str, create: bool = False) -> Optional[PayeeIntel]:
        intel = self._payees.get(account_id)
        if intel is not None:
            self._payees.move_to_end(account_id)
        elif create:
            intel = self._payees[account_id] = PayeeIntel(account_id)
            while len(self._payees) > self._max_payees:
                self._payees.popitem(last=False)
        return intel

    def commit_payment(
        self,
        payer: str,
        payee: str,
        amount: float,
        at: float,
        device: str = "",
        place: str = "",
        session: Optional[Dict] = None,
        typing_ms: Optional[float] = None,
    ) -> None:
        self.customer(payer, create=True).commit(payee, amount, at, device, place, session, typing_ms)
        intel = self.payee(payee, create=True)
        if not intel.first_seen:
            intel.first_seen = at
        intel.first_seen = min(intel.first_seen, at)
        intel.inbound.append((at, payer))
        intel.first_payment_by.setdefault(payer, at)
        intel.inbound_total += amount
        sender = self.payee(payer)
        if sender is not None:
            sender.outbound_total += amount

    @property
    def sizes(self) -> Dict[str, int]:
        return {"customers": len(self._customers), "payees": len(self._payees)}
