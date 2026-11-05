"""The most recent real public payments seen by any live stream, for the Detection modules findings.

Every scored event from the live payment feed is appended here, so the modules can report what they
find in real traffic instead of in a synthetic dataset. Bounded and in memory: it starts empty on each
deploy and fills while someone watches a live view.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Dict, List

MAX_PAYMENTS = 3000


class LiveBuffer:
    def __init__(self, max_payments: int = MAX_PAYMENTS):
        self._events: Deque[Dict] = deque(maxlen=max_payments)
        self._seen: set = set()
        self._lock = threading.Lock()

    def add(self, event: Dict) -> None:
        """Keep one scored event; the same payment seen by two viewers is kept once."""
        payment = event.get("payment") or {}
        txn_id = payment.get("txn_id")
        if not txn_id:
            return
        with self._lock:
            if txn_id in self._seen:
                return
            if len(self._events) == self._events.maxlen:
                self._seen.discard(self._events[0]["payment"]["txn_id"])
            self._seen.add(txn_id)
            self._events.append(
                {
                    "payment": dict(payment),
                    "decision": event.get("decision"),
                    "case_id": event.get("case_id"),
                    "ring_members": list(event.get("ring_members") or []),
                    "reasons": list(event.get("reasons") or []),
                }
            )

    def snapshot(self) -> List[Dict]:
        with self._lock:
            return list(self._events)

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
