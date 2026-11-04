"""
Device Profiling Service
=========================
Longitudinal device tracking per account. Detects device switching,
shared devices across accounts, and emulator/rooting risk.

Signals:
  DP01: Multiple devices per account
  DP02: Rapid device switching (multiple in 24h)
  DP03: Device shared across flagged accounts
  DP04: Emulator or rooted device indicators
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeviceTrustResult:
    account_id: str
    device_trust_score: float  # 0.0 (trusted) to 1.0 (untrusted)
    device_count: int
    recent_switches_24h: int
    shared_device_accounts: Tuple[str, ...]
    reason_codes: Tuple[str, ...]


# Known emulator/rooting indicators in device fingerprints
EMULATOR_INDICATORS = frozenset(
    {
        "generic",
        "emulator",
        "sdk_gphone",
        "vbox",
        "goldfish",
        "rooted",
        "magisk",
        "supersu",
        "xposed",
    }
)


class DeviceProfiler:
    """Maintains device history per account and device-to-accounts mapping."""

    def __init__(self):
        # account_id -> list of (device_id, timestamp) tuples
        self._account_devices: Dict[str, List[Tuple[str, float]]] = {}
        # device_id -> set of account_ids
        self._device_accounts: Dict[str, Set[str]] = {}
        # account_id -> set of flagged account_ids sharing devices
        self._flagged_accounts: Set[str] = set()
        # Only categorical risk flags are retained; raw browser attributes are
        # intentionally not stored.
        self._device_risk_indicators: Dict[str, Set[str]] = {}

    def record_device_event(
        self,
        account_id: str,
        device_id: str,
        timestamp: float = None,
        is_flagged: bool = False,
        risk_indicators: Tuple[str, ...] = (),
    ) -> None:
        """Record a device usage event for an account."""
        ts = timestamp or time.time()

        self._account_devices.setdefault(account_id, []).append((device_id, ts))
        self._device_accounts.setdefault(device_id, set()).add(account_id)
        if risk_indicators:
            self._device_risk_indicators.setdefault(device_id, set()).update(
                indicator.lower() for indicator in risk_indicators
            )

        if is_flagged:
            self._flagged_accounts.add(account_id)

    def compute_trust(self, account_id: str) -> DeviceTrustResult:
        """Compute device trust score for an account."""
        events = self._account_devices.get(account_id, [])
        reason_codes: List[str] = []
        scores: List[float] = []

        # DP01: Multiple devices per account
        unique_devices = set(dev_id for dev_id, _ in events)
        device_count = len(unique_devices)
        if device_count >= 4:
            scores.append(0.9)
            reason_codes.append(f"DP01: {device_count} different devices used on this account")
        elif device_count >= 2:
            scores.append(0.4)
            reason_codes.append(f"DP01: {device_count} different devices used on this account")

        # DP02: Rapid device switching (multiple in 24h)
        recent_switches = self._count_recent_switches(events, window_hours=24)
        if recent_switches >= 3:
            scores.append(0.85)
            reason_codes.append(f"DP02: {recent_switches} device switches in 24h")
        elif recent_switches >= 2:
            scores.append(0.5)
            reason_codes.append(f"DP02: {recent_switches} device switches in 24h")

        # DP03: Device shared across flagged accounts
        shared_flagged = self._find_shared_flagged(account_id)
        if shared_flagged:
            scores.append(min(1.0, 0.3 * len(shared_flagged)))
            reason_codes.append(f"DP03: Device shared with {len(shared_flagged)} flagged account(s)")

        # DP04: Emulator or rooted device indicators
        emulator_detected = any(
            self._is_emulator(dev_id) or bool(self._device_risk_indicators.get(dev_id, set()) & {"emulator", "rooted"})
            for dev_id in unique_devices
        )
        if emulator_detected:
            scores.append(0.7)
            reason_codes.append("DP04: Emulator or rooted device detected")

        bot_detected = any("bot" in self._device_risk_indicators.get(dev_id, set()) for dev_id in unique_devices)
        if bot_detected:
            scores.append(0.75)
            reason_codes.append("DP05: Automated browser or bot signal detected")

        # Composite trust score (0 = trusted, 1 = untrusted)
        trust_score = 0.0
        if scores:
            # Weighted: max contributes 60%, mean contributes 40%
            trust_score = 0.6 * max(scores) + 0.4 * (sum(scores) / len(scores))
            trust_score = min(trust_score, 1.0)

        return DeviceTrustResult(
            account_id=account_id,
            device_trust_score=round(trust_score, 4),
            device_count=device_count,
            recent_switches_24h=recent_switches,
            shared_device_accounts=tuple(shared_flagged),
            reason_codes=tuple(reason_codes),
        )

    def _count_recent_switches(
        self,
        events: List[Tuple[str, float]],
        window_hours: int = 24,
    ) -> int:
        """Count unique device switches within a time window."""
        if len(events) < 2:
            return 0
        cutoff = time.time() - (window_hours * 3600)
        recent = [(dev, ts) for dev, ts in events if ts >= cutoff]
        if len(recent) < 2:
            return 0
        recent.sort(key=lambda x: x[1])
        switches = sum(1 for i in range(1, len(recent)) if recent[i][0] != recent[i - 1][0])
        return switches

    def _find_shared_flagged(self, account_id: str) -> List[str]:
        """Find flagged accounts sharing any device with this account."""
        my_devices = set(dev_id for dev_id, _ in self._account_devices.get(account_id, []))
        shared = set()
        for dev_id in my_devices:
            for other_acc in self._device_accounts.get(dev_id, set()):
                if other_acc != account_id and other_acc in self._flagged_accounts:
                    shared.add(other_acc)
        return sorted(shared)

    @staticmethod
    def _is_emulator(device_id: str) -> bool:
        """Check if device ID contains emulator/rooting indicators."""
        lower = device_id.lower()
        return any(indicator in lower for indicator in EMULATOR_INDICATORS)

    def get_device_stats(self) -> Dict:
        """Return aggregate device profiling statistics."""
        return {
            "total_accounts_tracked": len(self._account_devices),
            "total_devices_seen": len(self._device_accounts),
            "flagged_accounts": len(self._flagged_accounts),
        }
