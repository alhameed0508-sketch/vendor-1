"""Feature 1: Session Integrity & Device Trust.

Looks at the session behind a payment, not only at the device. A fraudster with stolen credentials on
a device the customer has used before still shows up through the takeover sequence (credential or SIM
change, login from a new place, payee added, payment), impossible travel, a session that changes device
or IP midway, or a typing rhythm that is not the customer's.

Codes SD01-SD10 match docs/SYSTEM_DESIGN.md section 6.3.2.
"""

from __future__ import annotations

import math
import statistics
from typing import Dict, List, Mapping, Optional

from intelligence.contracts import SESSION, STRONG, WEAK, EngineResult, Reason
from intelligence.profiles import CustomerProfile, event_seconds
from intelligence.threat_feeds import ThreatFeeds

from models.device.device_profiler import EMULATOR_INDICATORS, DeviceProfiler

TAKEOVER_EVENTS = frozenset(
    {"password_reset", "credential_change", "sim_change", "mobile_number_change", "device_binding", "mpin_reset"}
)
TAKEOVER_WINDOW_S = 30 * 60
IMPOSSIBLE_KMH = 900.0
MIN_TRAVEL_KM = 50.0
SHARED_DEVICE_MIN = 3
RISKY_FLAGS = frozenset({"emulator", "rooted", "jailbroken", "automation", "bot", "hooking", "cloned_app"})


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


class SessionIntegrityEngine:
    def __init__(self, devices: Optional[DeviceProfiler] = None, feeds: Optional[ThreatFeeds] = None):
        self.devices = devices or DeviceProfiler()
        self.feeds = feeds

    def assess(
        self,
        payer: str,
        at: float,
        session: Optional[Mapping],
        profile: Optional[CustomerProfile],
        payee_added_at: Optional[float] = None,
    ) -> EngineResult:
        if not session:
            return EngineResult(
                SESSION,
                (),
                data_available=False,
                note="no session data for this payment (for example a public blockchain payment)",
            )
        reasons: List[Reason] = []
        device = str(session.get("device_id") or "")
        has_history = profile is not None and profile.n_payments > 0
        new_device = (
            bool(device) and has_history and device not in profile.devices and device not in profile.trusted_devices
        )
        if new_device:
            reasons.append(Reason("SD01", "Device not seen before for this customer.", 0.20, WEAK))

        if device:
            others = self.devices.accounts_on_device(device) - {payer}
            if len(others) >= SHARED_DEVICE_MIN:
                reasons.append(
                    Reason(
                        "SD02",
                        f"Device also used by {len(others)} other customers.",
                        min(0.7, 0.45 + 0.05 * (len(others) - SHARED_DEVICE_MIN)),
                        STRONG,
                    )
                )

        flags = {str(f).lower() for f in session.get("device_flags") or ()}
        risky = sorted(flags & RISKY_FLAGS)
        if not risky and device and any(ind in device.lower() for ind in EMULATOR_INDICATORS):
            risky = ["emulator-like device id"]
        if risky:
            reasons.append(Reason("SD03", f"Device fingerprint shows {', '.join(risky)}.", 0.60, STRONG))

        ip = session.get("ip")
        if ip and self.feeds is not None:
            for hit in self.feeds.lookup(ip):
                if hit["feed"] == "tor_exit":
                    reasons.append(Reason("SD04", f"IP {ip} is a Tor exit node (Tor Project list).", 0.45, STRONG))
                else:
                    reasons.append(
                        Reason(
                            "SD05",
                            f"IP {ip} is inside {hit['match']}, a hijacked network on Spamhaus DROP.",
                            0.55,
                            STRONG,
                        )
                    )

        last = profile.last_session if profile else None
        lat, lon = session.get("lat"), session.get("lon")
        new_place = False
        if last and lat is not None and lon is not None and last.get("lat") is not None and last.get("lon") is not None:
            km = haversine_km(float(last["lat"]), float(last["lon"]), float(lat), float(lon))
            hours = max((at - float(last["at"])) / 3600.0, 1 / 60)
            new_place = km >= MIN_TRAVEL_KM
            if km >= MIN_TRAVEL_KM and km / hours > IMPOSSIBLE_KMH:
                reasons.append(
                    Reason(
                        "SD06",
                        f"Impossible travel: {km:,.0f} km from the last session in {hours * 60:,.0f} min.",
                        0.60,
                        STRONG,
                    )
                )
        city = session.get("city")
        if city and profile and profile.places and city not in profile.places:
            new_place = True

        if last and session.get("session_id") and last.get("session_id") == session.get("session_id"):
            changed = [k for k in ("device_id", "ip") if session.get(k) and last.get(k) and session[k] != last[k]]
            if "device_id" in changed:
                reasons.append(
                    Reason("SD07", f"The {' and '.join(changed)} changed inside the same session.", 0.40, STRONG)
                )
            elif changed:
                # Phones hop between Wi-Fi and mobile data and carriers re-NAT: an IP change alone is routine.
                reasons.append(
                    Reason(
                        "SD07",
                        "The IP address changed inside the same session (common on mobile networks).",
                        0.10,
                        WEAK,
                    )
                )

        takeover = self._takeover(session.get("auth_events") or (), at, new_device or new_place, payee_added_at)
        if takeover:
            reasons.append(takeover)

        if session.get("remote_access"):
            reasons.append(Reason("SD09", "A remote-access app was active during the payment.", 0.55, STRONG))

        typing = session.get("typing_ms_per_char")
        if typing and profile and len(profile.typing_ms) >= 5:
            med = statistics.median(profile.typing_ms)
            mad = max(statistics.median(abs(x - med) for x in profile.typing_ms) * 1.4826, 10.0)
            z = abs(float(typing) - med) / mad
            if z >= 3:
                reasons.append(
                    Reason(
                        "SD10",
                        f"Typing rhythm {float(typing):.0f} ms/char vs the customer's usual {med:.0f}.",
                        0.35,
                        WEAK,
                    )
                )

        features = {"new_device": float(new_device), "new_place": float(new_place)}
        return EngineResult(SESSION, tuple(reasons), True, features)

    @staticmethod
    def _takeover(auth_events, at: float, new_login: bool, payee_added_at: Optional[float]) -> Optional[Reason]:
        recent = []
        for ev in auth_events:
            kind = str(ev.get("type", "")).lower()
            try:
                when = event_seconds(ev.get("at"))
            except (TypeError, ValueError):
                continue
            if kind in TAKEOVER_EVENTS and 0 <= at - when <= TAKEOVER_WINDOW_S:
                recent.append(kind)
        if not recent:
            return None
        payee_new = payee_added_at is not None and 0 <= at - payee_added_at <= TAKEOVER_WINDOW_S
        steps = ", ".join(sorted(set(recent)))
        if new_login and payee_new:
            return Reason(
                "SD08",
                f"Takeover sequence within 30 min: {steps} → login from a new device or place → payee added → payment.",
                0.85,
                STRONG,
            )
        if payee_new or new_login:
            return Reason(
                "SD08",
                f"Part of a takeover sequence within 30 min: {steps}, then "
                f"{'a new payee' if payee_new else 'a new device or place'}.",
                0.55,
                STRONG,
            )
        return None

    def commit(self, payer: str, at: float, session: Optional[Mapping]) -> None:
        if not session or not session.get("device_id"):
            return
        flags = tuple(str(f).lower() for f in session.get("device_flags") or ())
        self.devices.record_device_event(payer, str(session["device_id"]), timestamp=at, risk_indicators=flags)


def session_snapshot(session: Optional[Mapping]) -> Optional[Dict]:
    """What the profile keeps from a session: no raw fingerprints or biometrics."""
    if not session:
        return None
    return {k: session.get(k) for k in ("session_id", "device_id", "ip", "lat", "lon", "city")}
