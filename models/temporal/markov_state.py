"""
Markov State Transition Scorer for Money Mule Detection
========================================================
Captures the canonical mule lifecycle via Markov chain state-transition
modeling.  Research (MuleTrack, NPCI/Springer) establishes that temporal
phase transitions are the single most predictive signal for mule
detection -- 75 % of mule accounts evade onboarding screening and only
reveal themselves through behavioral state changes over an 8-month
median horizon.

Lifecycle states:

    DORMANT -> LOW_ACTIVITY -> RECEIVING -> FORWARDING -> SWEEP -> (back to DORMANT)

Key transitions flagged (thresholds tuned for self-loop dilution):
    P(RECEIVING | DORMANT)    >= 0.15 -- activation
    P(FORWARDING | RECEIVING) >= 0.15 -- mule behavior
    P(SWEEP | FORWARDING)     >= 0.15 -- fund clearance

Reason codes: MK01 .. MK05 (see ``MarkovStateScorer.score_account``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Canonical mule lifecycle -- the ordered sequence of states that a
# textbook money mule account traverses.
_CANONICAL_LIFECYCLE: Tuple[str, ...] = ("DORMANT", "RECEIVING", "FORWARDING", "SWEEP")

# Thresholds for the three key transitions that signal mule behavior.
# These are intentionally set to detect transitions even when self-loop
# dilution reduces raw probabilities (e.g., 4 weeks in RECEIVING followed
# by 4 weeks in FORWARDING yields P(FORWARDING|RECEIVING) = 0.25).
_ACTIVATION_THRESHOLD = 0.15      # P(RECEIVING | DORMANT)
_MULE_BEHAVIOR_THRESHOLD = 0.15   # P(FORWARDING | RECEIVING)
_FUND_CLEARANCE_THRESHOLD = 0.15  # P(SWEEP | FORWARDING)

# Rapid lifecycle progression -- if an account traverses DORMANT->SWEEP
# in fewer than this many weeks, it is flagged.
_RAPID_LIFECYCLE_WEEKS = 4

# Minimum number of completed DORMANT->SWEEP cycles to flag as cyclic.
_MIN_CYCLE_COUNT = 2


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------

class AccountState(Enum):
    """Observable account states in the mule lifecycle."""

    DORMANT = "DORMANT"
    LOW_ACTIVITY = "LOW_ACTIVITY"
    RECEIVING = "RECEIVING"
    FORWARDING = "FORWARDING"
    SWEEP = "SWEEP"


# ---------------------------------------------------------------------------
# Immutable result data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarkovTransitionMatrix:
    """Observed transition probabilities between account states.

    ``probabilities`` maps (from_state, to_state) -> probability.
    ``state_counts`` maps state -> number of windows observed in that state.
    """

    probabilities: Tuple[Tuple[str, str, float], ...]
    state_counts: Tuple[Tuple[str, int], ...]

    def get_probability(self, from_state: str, to_state: str) -> float:
        """Look up P(to_state | from_state)."""
        for f, t, p in self.probabilities:
            if f == from_state and t == to_state:
                return p
        return 0.0


@dataclass(frozen=True)
class MarkovStateResult:
    """Scoring result for a single account."""

    account_id: str
    current_state: str
    state_history: Tuple[str, ...]
    transition_score: float          # 0-1 composite risk score
    mule_lifecycle_probability: float  # 0-1 how closely transitions match canonical lifecycle
    reason_codes: Tuple[str, ...]


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class MarkovStateScorer:
    """Score accounts by modelling their temporal state transitions as a
    Markov chain and comparing the observed transition matrix against the
    canonical mule lifecycle.
    """

    # Weights for the three key transitions when computing lifecycle score.
    _LIFECYCLE_WEIGHTS: Dict[Tuple[str, str], float] = {
        ("DORMANT", "RECEIVING"): 0.30,
        ("RECEIVING", "FORWARDING"): 0.40,
        ("FORWARDING", "SWEEP"): 0.30,
    }

    # ------------------------------------------------------------------
    # State classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_state(
        account: Dict,
        transactions: List[Dict],
        in_transactions: List[Dict],
        window_start: datetime,
        window_end: datetime,
    ) -> AccountState:
        """Classify the account state for a single time window.

        Parameters
        ----------
        account:
            Account metadata dict (must contain ``account_id``).
        transactions:
            Outgoing transactions for this account.
        in_transactions:
            Incoming transactions for this account.
        window_start / window_end:
            The boundaries of the time window.

        Returns
        -------
        AccountState
            The classified state.
        """
        window_out = _filter_window(transactions, window_start, window_end)
        window_in = _filter_window(in_transactions, window_start, window_end)

        total_txn_count = len(window_out) + len(window_in)

        # DORMANT: fewer than 2 transactions in the window
        if total_txn_count < 2:
            return AccountState.DORMANT

        total_incoming = sum(float(t.get("amount", 0)) for t in window_in)
        total_outgoing = sum(float(t.get("amount", 0)) for t in window_out)

        # SWEEP: outgoing/incoming > 0.9 AND balance approaches zero
        if total_incoming > 0 and total_outgoing > 0:
            out_in_ratio = total_outgoing / total_incoming
            balance = total_incoming - total_outgoing
            # Balance is near zero relative to inflow
            near_zero = abs(balance) < total_incoming * 0.15
            if out_in_ratio > 0.9 and near_zero:
                return AccountState.SWEEP

        # FORWARDING: meaningful pass-through behavior
        # Requires: (a) both inflow and outflow present, (b) outgoing is
        # a significant fraction of incoming (pass-through > 0.7), and
        # (c) outflow does NOT exceed inflow (that would be spending down
        # savings, not forwarding received funds).
        if total_incoming > 0 and total_outgoing > 0:
            pass_through_ratio = total_outgoing / total_incoming
            if 0.7 < pass_through_ratio <= 0.9 and len(window_out) >= 2:
                return AccountState.FORWARDING

        # RECEIVING: incoming dominates outgoing
        if total_incoming > total_outgoing * 2:
            return AccountState.RECEIVING

        # LOW_ACTIVITY: few transactions or balanced modest flow
        if total_txn_count <= 5:
            return AccountState.LOW_ACTIVITY

        # Fallback -- moderate activity that doesn't match the above patterns
        return AccountState.LOW_ACTIVITY

    # ------------------------------------------------------------------
    # Transition matrix computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_transition_matrix(
        state_history: Sequence[str],
    ) -> MarkovTransitionMatrix:
        """Compute transition probabilities from an observed state sequence.

        Parameters
        ----------
        state_history:
            Ordered sequence of state names (one per time window).

        Returns
        -------
        MarkovTransitionMatrix
            Frozen dataclass with transition probabilities and counts.
        """
        all_states = [s.value for s in AccountState]

        # Count state occurrences
        state_counts: Dict[str, int] = {s: 0 for s in all_states}
        for s in state_history:
            state_counts[s] = state_counts.get(s, 0) + 1

        # Count transitions
        transition_counts: Dict[Tuple[str, str], int] = {}
        from_counts: Dict[str, int] = {}
        for i in range(len(state_history) - 1):
            from_s = state_history[i]
            to_s = state_history[i + 1]
            key = (from_s, to_s)
            transition_counts[key] = transition_counts.get(key, 0) + 1
            from_counts[from_s] = from_counts.get(from_s, 0) + 1

        # Compute probabilities
        probs: List[Tuple[str, str, float]] = []
        for from_s in all_states:
            total_from = from_counts.get(from_s, 0)
            for to_s in all_states:
                count = transition_counts.get((from_s, to_s), 0)
                prob = count / total_from if total_from > 0 else 0.0
                if prob > 0.0:
                    probs.append((from_s, to_s, round(prob, 4)))

        return MarkovTransitionMatrix(
            probabilities=tuple(probs),
            state_counts=tuple(sorted(state_counts.items())),
        )

    # ------------------------------------------------------------------
    # Lifecycle scoring
    # ------------------------------------------------------------------

    @classmethod
    def _score_mule_lifecycle(
        cls,
        matrix: MarkovTransitionMatrix,
    ) -> float:
        """Score how closely observed transitions match the canonical
        mule lifecycle (DORMANT -> RECEIVING -> FORWARDING -> SWEEP).

        Returns a float in [0, 1].
        """
        score = 0.0
        for (from_s, to_s), weight in cls._LIFECYCLE_WEIGHTS.items():
            prob = matrix.get_probability(from_s, to_s)
            # Threshold-gated contribution: only count when above the
            # known mule threshold for that transition.
            thresholds = {
                ("DORMANT", "RECEIVING"): _ACTIVATION_THRESHOLD,
                ("RECEIVING", "FORWARDING"): _MULE_BEHAVIOR_THRESHOLD,
                ("FORWARDING", "SWEEP"): _FUND_CLEARANCE_THRESHOLD,
            }
            threshold = thresholds.get((from_s, to_s), 0.0)
            if prob >= threshold:
                # Scale contribution: at threshold = 0, at 1.0 = full weight
                contribution = min(prob / 1.0, 1.0) * weight
                score += contribution

        return round(min(score, 1.0), 4)

    # ------------------------------------------------------------------
    # Reason code generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_reason_codes(
        matrix: MarkovTransitionMatrix,
        state_history: Sequence[str],
    ) -> Tuple[str, ...]:
        """Generate MK01..MK05 reason codes from the transition matrix
        and observed state history.
        """
        codes: List[str] = []

        p_recv_given_dormant = matrix.get_probability("DORMANT", "RECEIVING")
        p_fwd_given_recv = matrix.get_probability("RECEIVING", "FORWARDING")
        p_sweep_given_fwd = matrix.get_probability("FORWARDING", "SWEEP")

        if p_recv_given_dormant >= _ACTIVATION_THRESHOLD:
            codes.append(
                f"MK01: Dormant-to-receiving transition detected "
                f"(P={p_recv_given_dormant:.2f})"
            )

        if p_fwd_given_recv >= _MULE_BEHAVIOR_THRESHOLD:
            codes.append(
                f"MK02: Receiving-to-forwarding pattern — mule activation "
                f"(P={p_fwd_given_recv:.2f})"
            )

        if p_sweep_given_fwd >= _FUND_CLEARANCE_THRESHOLD:
            codes.append(
                f"MK03: Sweep behavior after forwarding phase "
                f"(P={p_sweep_given_fwd:.2f})"
            )

        # MK04: Rapid lifecycle progression -- DORMANT->SWEEP in < _RAPID_LIFECYCLE_WEEKS
        if len(state_history) >= 2:
            first_dormant_idx: Optional[int] = None
            first_sweep_idx: Optional[int] = None
            for i, s in enumerate(state_history):
                if s == "DORMANT" and first_dormant_idx is None:
                    first_dormant_idx = i
                if s == "SWEEP" and first_dormant_idx is not None:
                    first_sweep_idx = i
                    break
            if first_dormant_idx is not None and first_sweep_idx is not None:
                weeks_elapsed = first_sweep_idx - first_dormant_idx
                if weeks_elapsed < _RAPID_LIFECYCLE_WEEKS:
                    codes.append(
                        f"MK04: Rapid lifecycle progression — DORMANT to SWEEP "
                        f"in {weeks_elapsed} week(s)"
                    )

        # MK05: Cyclic mule pattern -- repeated DORMANT->SWEEP cycles
        cycle_count = _count_dormant_sweep_cycles(state_history)
        if cycle_count >= _MIN_CYCLE_COUNT:
            codes.append(
                f"MK05: Cyclic mule pattern — {cycle_count} completed "
                f"DORMANT-to-SWEEP cycles detected"
            )

        return tuple(codes)

    # ------------------------------------------------------------------
    # Public scoring API
    # ------------------------------------------------------------------

    def score_account(
        self,
        account_id: str,
        account: Dict,
        transactions: List[Dict],
        in_transactions: List[Dict],
        window_weeks: int = 24,
    ) -> MarkovStateResult:
        """Score a single account for mule lifecycle behavior.

        Parameters
        ----------
        account_id:
            Unique account identifier.
        account:
            Account metadata dict.
        transactions:
            Outgoing transactions (must have ``timestamp`` and ``amount``).
        in_transactions:
            Incoming transactions (must have ``timestamp`` and ``amount``).
        window_weeks:
            Number of weekly windows to analyse (default 24 = ~6 months).

        Returns
        -------
        MarkovStateResult
            Frozen result with transition_score, lifecycle probability,
            state history, and reason codes.
        """
        all_txns = transactions + in_transactions
        if not all_txns:
            logger.debug("No transactions for account %s — returning zero score", account_id)
            return _zero_result(account_id)

        # Determine time range from transaction timestamps
        timestamps = _extract_timestamps(all_txns)
        if not timestamps:
            logger.warning(
                "No parseable timestamps for account %s — returning zero score",
                account_id,
            )
            return _zero_result(account_id)

        earliest = min(timestamps)
        latest = max(timestamps)

        # Build weekly windows (at most window_weeks)
        windows = _build_weekly_windows(earliest, latest, window_weeks)
        if not windows:
            logger.debug("Insufficient time span for account %s", account_id)
            return _zero_result(account_id)

        # Classify state for each window
        state_history: List[str] = []
        for w_start, w_end in windows:
            state = self._classify_state(
                account, transactions, in_transactions, w_start, w_end,
            )
            state_history.append(state.value)

        # If only one window, we cannot compute transitions
        if len(state_history) < 2:
            current = state_history[-1] if state_history else AccountState.DORMANT.value
            return MarkovStateResult(
                account_id=account_id,
                current_state=current,
                state_history=tuple(state_history),
                transition_score=0.0,
                mule_lifecycle_probability=0.0,
                reason_codes=(),
            )

        # Compute transition matrix
        matrix = self._compute_transition_matrix(state_history)

        # Score lifecycle match
        lifecycle_prob = self._score_mule_lifecycle(matrix)

        # Generate reason codes
        reason_codes = self._generate_reason_codes(matrix, state_history)

        # Composite transition score: lifecycle probability is the primary
        # signal, boosted by reason-code density.
        reason_boost = min(len(reason_codes) * 0.08, 0.25)
        transition_score = round(min(lifecycle_prob + reason_boost, 1.0), 4)

        current_state = state_history[-1]

        return MarkovStateResult(
            account_id=account_id,
            current_state=current_state,
            state_history=tuple(state_history),
            transition_score=transition_score,
            mule_lifecycle_probability=lifecycle_prob,
            reason_codes=reason_codes,
        )

    def score_batch(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
    ) -> Dict[str, MarkovStateResult]:
        """Score multiple accounts in batch.

        Parameters
        ----------
        accounts:
            List of account metadata dicts (each must have ``account_id``).
        transactions:
            All transactions (must have ``from_account``, ``to_account``,
            ``timestamp``, ``amount``).

        Returns
        -------
        Dict mapping account_id -> MarkovStateResult.
        """
        # Group transactions by account
        outgoing: Dict[str, List[Dict]] = {}
        incoming: Dict[str, List[Dict]] = {}
        for t in transactions:
            from_acc = t.get("from_account", "")
            to_acc = t.get("to_account", "")
            outgoing.setdefault(from_acc, []).append(t)
            incoming.setdefault(to_acc, []).append(t)

        acc_map = {a["account_id"]: a for a in accounts}
        results: Dict[str, MarkovStateResult] = {}

        for acc_id, acc in acc_map.items():
            out_txns = outgoing.get(acc_id, [])
            in_txns = incoming.get(acc_id, [])
            results[acc_id] = self.score_account(
                acc_id, acc, out_txns, in_txns,
            )

        return results


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------

def _zero_result(account_id: str) -> MarkovStateResult:
    """Return a zero-score result for insufficient data."""
    return MarkovStateResult(
        account_id=account_id,
        current_state=AccountState.DORMANT.value,
        state_history=(),
        transition_score=0.0,
        mule_lifecycle_probability=0.0,
        reason_codes=(),
    )


def _parse_timestamp(raw: object) -> Optional[datetime]:
    """Best-effort timestamp parser that handles ISO-8601 strings and
    ``datetime`` objects.  Returns ``None`` on failure.
    """
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        # Handle trailing 'Z' (UTC marker)
        cleaned = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def _extract_timestamps(transactions: List[Dict]) -> List[datetime]:
    """Extract parseable timestamps from a list of transaction dicts."""
    result: List[datetime] = []
    for t in transactions:
        ts = _parse_timestamp(t.get("timestamp"))
        if ts is not None:
            result.append(ts)
    return result


def _filter_window(
    transactions: List[Dict],
    window_start: datetime,
    window_end: datetime,
) -> List[Dict]:
    """Return transactions whose timestamp falls within [start, end)."""
    result: List[Dict] = []
    for t in transactions:
        ts = _parse_timestamp(t.get("timestamp"))
        if ts is not None and window_start <= ts < window_end:
            result.append(t)
    return result


def _build_weekly_windows(
    earliest: datetime,
    latest: datetime,
    max_windows: int,
) -> List[Tuple[datetime, datetime]]:
    """Build a list of (start, end) weekly windows, most recent last.

    If the total span produces more than ``max_windows`` windows, only
    the most recent ``max_windows`` are returned.
    """
    one_week = timedelta(weeks=1)
    # Extend latest to include the final partial week
    end = latest + one_week

    windows: List[Tuple[datetime, datetime]] = []
    cursor = earliest
    while cursor < end:
        w_end = cursor + one_week
        windows.append((cursor, w_end))
        cursor = w_end

    # Keep only the most recent max_windows
    if len(windows) > max_windows:
        windows = windows[-max_windows:]

    return windows


def _count_dormant_sweep_cycles(state_history: Sequence[str]) -> int:
    """Count completed DORMANT -> ... -> SWEEP cycles in the history.

    A cycle starts at a DORMANT state and completes when a SWEEP state
    is encountered (possibly with intermediate states).
    """
    cycles = 0
    in_cycle = False
    for s in state_history:
        if s == "DORMANT":
            in_cycle = True
        elif s == "SWEEP" and in_cycle:
            cycles += 1
            in_cycle = False
    return cycles
