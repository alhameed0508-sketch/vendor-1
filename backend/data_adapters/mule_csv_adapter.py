"""
Mule CSV adapter — parses pipe-delimited CBS transaction data to MuleCatch format.

CBS schema (pipe-delimited):
  TRAN_DATE, TRAN_ID, TRAN_TYPE, TRAN_SUB_TYPE, PART_TRAN_TYPE,
  ACID, TRAN_AMT, balance, channel, CIF_ID, ACCT_OPN_DATE,
  LIEN_AMT, customer_age

MuleCatch format:
  Transactions: txn_id, from_account, to_account, amount, timestamp, ...
  Accounts: account_id, role, bank, city, account_age_days, kyc_status, ...
"""

from __future__ import annotations

import csv
import hashlib
import logging
from collections import defaultdict
from datetime import datetime
from io import StringIO
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Channel → MuleCatch transaction type mapping
CHANNEL_TYPE_MAP = {
    "UPI": "UPI_PUSH",
    "MB": "MOBILE_BANKING",
    "IMPS_other": "IMPS",
    "IMPS": "IMPS",
    "NEFT": "NEFT",
    "RTGS": "RTGS",
    "ATM": "ATM_WITHDRAWAL",
    "BNA": "CASH_DEPOSIT",
}

CBS_DATE_FORMAT = "%d/%m/%Y %H:%M"
REQUIRED_CBS_COLUMNS = {
    "TRAN_DATE",
    "TRAN_ID",
    "TRAN_TYPE",
    "TRAN_SUB_TYPE",
    "PART_TRAN_TYPE",
    "ACID",
    "TRAN_AMT",
    "balance",
    "channel",
    "CIF_ID",
    "ACCT_OPN_DATE",
    "LIEN_AMT",
    "customer_age",
}


def row_date_key(row: Dict) -> str:
    """Extract date-only key (DD/MM/YYYY) from a CBS row for grouping."""
    return row.get("TRAN_DATE", "").strip()[:10]


class MuleCSVAdapter:
    """Parses pipe-delimited CBS CSV and maps to MuleCatch transaction/account format."""

    def parse(self, content: str, max_rows: int = 50000) -> Dict[str, List[Dict]]:
        """
        Parse pipe-delimited CSV content and return MuleCatch-format data.

        Args:
            content: Raw CSV file content (pipe-delimited)
            max_rows: Maximum rows to parse (0 = unlimited)

        Returns:
            Dict with keys "transactions" and "accounts"
        """
        raw_rows = self._read_rows(content.lstrip("\ufeff"), max_rows)
        transactions, linkage_strategy = self._map_transactions(raw_rows)
        accounts = self._derive_accounts(raw_rows)
        anomaly_flags = self._detect_anomaly_flags(raw_rows)
        data_quality = self._build_quality_report(
            raw_rows,
            transactions,
            linkage_strategy,
        )

        logger.info(
            "MuleCSV parsed: %d transactions, %d accounts, %d anomaly flags",
            len(transactions),
            len(accounts),
            len(anomaly_flags),
        )
        return {
            "transactions": transactions,
            "accounts": accounts,
            "anomaly_flags": anomaly_flags,
            "data_quality": data_quality,
        }

    @staticmethod
    def _read_rows(content: str, max_rows: int) -> List[Dict]:
        """Read pipe-delimited CSV rows into list of dicts."""
        reader = csv.DictReader(StringIO(content), delimiter="|")
        fieldnames = {name.strip() for name in (reader.fieldnames or []) if name}
        missing = sorted(REQUIRED_CBS_COLUMNS - fieldnames)
        if missing:
            raise ValueError(f"Missing required CBS columns: {', '.join(missing)}")

        rows: List[Dict] = []
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break
            rows.append(row)
        return rows

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse CBS date format DD/MM/YYYY HH:MM.

        Falls back to epoch on invalid input to avoid crashing the upload.
        """
        try:
            return datetime.strptime(date_str.strip(), CBS_DATE_FORMAT)
        except (ValueError, TypeError):
            logger.warning("Invalid CBS date format: %r, using epoch", date_str[:20])
            return datetime(2000, 1, 1)

    def _map_transactions(self, rows: List[Dict]) -> Tuple[List[Dict], str]:
        """Map CBS rows to MuleCatch transaction format.

        Linking strategy (applied in order of priority):
        1. TRAN_ID pairing: group rows by TRAN_ID. If a TRAN_ID has both a D and
           C leg across different accounts, link them directly.
        2. Amount-based flow inference: when step 1 produces no internal links
           (e.g., all TRAN_IDs are unique), match debit legs from one account
           with credit legs of another account by amount. This connects the
           internal accounts so Louvain community detection can find clusters.
        3. Remaining unmatched rows get an EXT_* counterparty.
        """
        all_acids = set(
            r.get("ACID", "").strip() for r in rows if r.get("ACID", "").strip()
        )

        transactions = self._try_tran_id_pairing(rows, all_acids)

        # Check if TRAN_ID pairing produced any internal links
        internal_links = sum(
            1
            for t in transactions
            if t["from_account"] in all_acids and t["to_account"] in all_acids
        )

        linkage_strategy = "TRAN_ID_PAIRING" if internal_links else "EXTERNAL_ONLY"
        if internal_links == 0 and len(all_acids) >= 2:
            # Fallback: amount-based flow inference
            logger.info(
                "No TRAN_ID-paired internal links found across %d accounts; "
                "falling back to amount-based flow inference",
                len(all_acids),
            )
            transactions = self._infer_flow_links(rows, all_acids)
            inferred_links = sum(
                1
                for transaction in transactions
                if transaction["from_account"] in all_acids
                and transaction["to_account"] in all_acids
            )
            if inferred_links:
                linkage_strategy = "AMOUNT_DATE_INFERENCE"

        return transactions, linkage_strategy

    @staticmethod
    def _build_quality_report(
        rows: List[Dict],
        transactions: List[Dict],
        linkage_strategy: str,
    ) -> Dict:
        """Describe linkage confidence and limitations of an uploaded dataset."""
        account_ids = {
            row.get("ACID", "").strip() for row in rows if row.get("ACID", "").strip()
        }
        internal_links = sum(
            1
            for transaction in transactions
            if transaction["from_account"] in account_ids
            and transaction["to_account"] in account_ids
        )
        debit_rows = sum(row.get("PART_TRAN_TYPE", "").strip() == "D" for row in rows)
        credit_rows = sum(row.get("PART_TRAN_TYPE", "").strip() == "C" for row in rows)
        transaction_ids = [
            row.get("TRAN_ID", "").strip()
            for row in rows
            if row.get("TRAN_ID", "").strip()
        ]
        distinct_timestamps = {
            row.get("TRAN_DATE", "").strip()
            for row in rows
            if row.get("TRAN_DATE", "").strip()
        }
        unknown_channels = sorted(
            {
                row.get("channel", "").strip()
                for row in rows
                if row.get("channel", "").strip() not in CHANNEL_TYPE_MAP
            }
        )

        warnings = ["GROUND_TRUTH_LABELS_ABSENT"]
        if len(distinct_timestamps) <= 1 and len(rows) > 1:
            warnings.append("TIMESTAMP_VARIETY_LOW")
        if linkage_strategy == "AMOUNT_DATE_INFERENCE":
            warnings.append("TRAN_ID_LINKAGE_UNAVAILABLE")
        smaller_leg = min(debit_rows, credit_rows)
        larger_leg = max(debit_rows, credit_rows)
        if larger_leg and smaller_leg / larger_leg < 0.2:
            warnings.append("DEBIT_CREDIT_IMBALANCE")
        if unknown_channels:
            warnings.append("UNKNOWN_CHANNELS")

        if linkage_strategy == "TRAN_ID_PAIRING":
            linkage_confidence = "HIGH"
        elif linkage_strategy == "AMOUNT_DATE_INFERENCE":
            linkage_confidence = "LOW" if len(distinct_timestamps) <= 1 else "MEDIUM"
        else:
            linkage_confidence = "LOW"

        return {
            "source_rows": len(rows),
            "mapped_transactions": len(transactions),
            "unique_accounts": len(account_ids),
            "unique_transaction_ids": len(set(transaction_ids)),
            "duplicate_transaction_id_rows": len(transaction_ids)
            - len(set(transaction_ids)),
            "debit_rows": debit_rows,
            "credit_rows": credit_rows,
            "distinct_timestamps": len(distinct_timestamps),
            "internal_links": internal_links,
            "external_transactions": len(transactions) - internal_links,
            "linkage_strategy": linkage_strategy,
            "linkage_confidence": linkage_confidence,
            "unknown_channels": unknown_channels,
            "warnings": warnings,
        }

    def _try_tran_id_pairing(self, rows: List[Dict], all_acids: set) -> List[Dict]:
        """Attempt to pair CBS rows by TRAN_ID (D + C legs)."""
        tran_groups: Dict[str, List[Dict]] = defaultdict(list)
        for row in rows:
            tran_id = row.get("TRAN_ID", "").strip()
            if tran_id:
                tran_groups[tran_id].append(row)

        transactions: List[Dict] = []
        seen_tran_ids: set = set()

        for tran_id, group in tran_groups.items():
            debit_legs = [
                r for r in group if r.get("PART_TRAN_TYPE", "").strip() == "D"
            ]
            credit_legs = [
                r for r in group if r.get("PART_TRAN_TYPE", "").strip() == "C"
            ]

            if debit_legs and credit_legs:
                # Paired internal transfer: link D account → C account
                for d_row in debit_legs:
                    for c_row in credit_legs:
                        pair_key = (
                            tran_id,
                            d_row.get("ACID", ""),
                            c_row.get("ACID", ""),
                        )
                        if pair_key in seen_tran_ids:
                            continue
                        seen_tran_ids.add(pair_key)
                        transactions.append(self._make_txn(d_row, c_row, tran_id))
            else:
                # Single-leg — assign EXT_* counterparty
                for row in group:
                    transactions.append(self._make_single_leg_txn(row, tran_id))

        return transactions

    def _infer_flow_links(self, rows: List[Dict], all_acids: set) -> List[Dict]:
        """Infer internal links by matching debit amounts to credit amounts.

        For each unique (date_key, amount) pair, if there are debits from one
        account and credits to another, link them. Each debit/credit row is
        used at most once. Unmatched rows get EXT_* counterparties.

        Preserves original row order: processes rows sequentially, resolving
        each row to either a matched internal link or a single-leg EXT_* txn.
        """
        # Build credit index for O(1) lookup by (date, amount)
        credit_index: Dict[Tuple, List[Dict]] = defaultdict(list)
        for row in rows:
            if row.get("PART_TRAN_TYPE", "").strip() == "C":
                date_key = row_date_key(row)
                amount = round(float(row.get("TRAN_AMT", 0)), 2)
                credit_index[(date_key, amount)].append(row)

        # First pass: build explicit debit→credit pair mapping
        matched_credit_ids: set = set()
        # Map debit row id → matched credit row
        debit_to_credit: Dict[int, Dict] = {}

        for row in rows:
            if row.get("PART_TRAN_TYPE", "").strip() != "D":
                continue

            d_acid = row.get("ACID", "").strip()
            date_key = row_date_key(row)
            amount = round(float(row.get("TRAN_AMT", 0)), 2)

            candidates = credit_index.get((date_key, amount), [])
            for c_row in candidates:
                c_acid = c_row.get("ACID", "").strip()
                if c_acid != d_acid and id(c_row) not in matched_credit_ids:
                    matched_credit_ids.add(id(c_row))
                    debit_to_credit[id(row)] = c_row
                    break

        # Second pass: emit transactions in original row order
        transactions: List[Dict] = []
        for row in rows:
            tran_id = row.get("TRAN_ID", "").strip()
            part_type = row.get("PART_TRAN_TYPE", "").strip()

            if part_type == "D" and id(row) in debit_to_credit:
                c_row = debit_to_credit[id(row)]
                transactions.append(self._make_txn(row, c_row, tran_id))
            elif part_type == "C" and id(row) in matched_credit_ids:
                continue  # consumed by a matched debit
            else:
                transactions.append(self._make_single_leg_txn(row, tran_id))

        internal_count = sum(
            1
            for t in transactions
            if t["from_account"] in all_acids and t["to_account"] in all_acids
        )
        logger.info(
            "Flow inference: %d internal links inferred across %d accounts",
            internal_count,
            len(all_acids),
        )

        return transactions

    def _make_txn(self, d_row: Dict, c_row: Dict, tran_id: str) -> Dict:
        """Build a MuleCatch transaction from paired D/C rows."""
        from_acid = d_row.get("ACID", "").strip()
        to_acid = c_row.get("ACID", "").strip()
        amount = float(d_row.get("TRAN_AMT", 0))
        channel = d_row.get("channel", "").strip()
        timestamp = self._parse_date(d_row["TRAN_DATE"]).isoformat()
        txn_type = CHANNEL_TYPE_MAP.get(channel, "UPI_PUSH")

        return {
            "txn_id": tran_id[:24] if len(tran_id) > 24 else tran_id,
            "from_account": from_acid,
            "to_account": to_acid,
            "amount": round(amount, 2),
            "timestamp": timestamp,
            "txn_type": txn_type,
            "is_suspicious": False,
            "pattern": "NORMAL",
            "device_id": "",
            "ip_address": "",
            "upi_id": "",
            "channel": channel,
            "part_tran_type": "D",
            "balance_after": float(d_row.get("balance", 0)),
        }

    def _make_single_leg_txn(self, row: Dict, tran_id: str) -> Dict:
        """Build a MuleCatch transaction with EXT_* counterparty."""
        acid = row.get("ACID", "").strip()
        part_type = row.get("PART_TRAN_TYPE", "").strip()
        channel = row.get("channel", "").strip()
        amount = float(row.get("TRAN_AMT", 0))
        timestamp = self._parse_date(row["TRAN_DATE"]).isoformat()

        counterparty = hashlib.sha256(
            f"counterparty_{tran_id}_{acid}".encode()
        ).hexdigest()[:16]
        counterparty_id = f"EXT_{counterparty.upper()}"

        if part_type == "D":
            from_account = acid
            to_account = counterparty_id
        else:
            from_account = counterparty_id
            to_account = acid

        txn_type = CHANNEL_TYPE_MAP.get(channel, "UPI_PUSH")

        return {
            "txn_id": tran_id[:24] if len(tran_id) > 24 else tran_id,
            "from_account": from_account,
            "to_account": to_account,
            "amount": round(amount, 2),
            "timestamp": timestamp,
            "txn_type": txn_type,
            "is_suspicious": False,
            "pattern": "NORMAL",
            "device_id": "",
            "ip_address": "",
            "upi_id": "",
            "channel": channel,
            "part_tran_type": part_type,
            "balance_after": float(row.get("balance", 0)),
        }

    def _derive_accounts(self, rows: List[Dict]) -> List[Dict]:
        """Derive account objects from CBS transaction rows.

        Computes per-account statistics including CBS-specific features:
        - pass_through_ratio: days with both credit AND debit / total active days
        - balance_volatility: std dev of balance across transactions
        - negative_balance_count: transactions where balance < 0
        - debit_credit_ratio: debit_volume / credit_volume (near 1.0 = pass-through)
        - max_single_txn_ratio: max_txn_amount / total_volume (layering indicator)
        """
        account_data: Dict[str, Dict] = {}

        for row in rows:
            acid = row.get("ACID", "").strip()
            if not acid:
                continue

            if acid not in account_data:
                account_data[acid] = {
                    "cif_id": row.get("CIF_ID", "").strip(),
                    "acct_opn_date": row.get("ACCT_OPN_DATE", "").strip(),
                    "customer_age": int(row.get("customer_age", 0) or 0),
                    "lien_amount": float(row.get("LIEN_AMT", 0) or 0),
                    "debit_count": 0,
                    "credit_count": 0,
                    "debit_volume": 0.0,
                    "credit_volume": 0.0,
                    "total_amount": 0.0,
                    "max_txn_amount": 0.0,
                    "balances": [],
                    "tran_dates": [],
                    "debit_days": set(),
                    "credit_days": set(),
                }

            info = account_data[acid]
            amount = float(row.get("TRAN_AMT", 0))
            part_type = row.get("PART_TRAN_TYPE", "").strip()

            # Extract day for pass-through ratio
            tran_date = row.get("TRAN_DATE", "").strip()
            day_key = tran_date[:10] if tran_date else ""

            if part_type == "D":
                info["debit_count"] += 1
                info["debit_volume"] += amount
                if day_key:
                    info["debit_days"].add(day_key)
            else:
                info["credit_count"] += 1
                info["credit_volume"] += amount
                if day_key:
                    info["credit_days"].add(day_key)

            info["total_amount"] += amount
            info["max_txn_amount"] = max(info["max_txn_amount"], amount)
            info["balances"].append(float(row.get("balance", 0)))

            if tran_date:
                info["tran_dates"].append(tran_date)

        accounts: List[Dict] = []
        for acid, info in account_data.items():
            txn_count = info["debit_count"] + info["credit_count"]
            avg_amount = info["total_amount"] / txn_count if txn_count > 0 else 0.0

            # Compute account age from opening date relative to latest transaction
            account_age_days = 0
            if info["acct_opn_date"] and info["tran_dates"]:
                try:
                    opn_date = self._parse_date(info["acct_opn_date"])
                    latest_txn = max(self._parse_date(d) for d in info["tran_dates"])
                    account_age_days = max(0, (latest_txn - opn_date).days)
                except (ValueError, TypeError):
                    account_age_days = 0

            # Correct avg_monthly_txn: divide by account age in months
            account_age_months = max(account_age_days / 30.0, 1.0)
            avg_monthly_txn = round(txn_count / account_age_months, 2)

            latest_balance = info["balances"][-1] if info["balances"] else 0.0

            # CBS-specific features
            # Pass-through ratio: days with both credit AND debit / total active days
            all_active_days = info["debit_days"] | info["credit_days"]
            pass_through_days = info["debit_days"] & info["credit_days"]
            pass_through_ratio = (
                len(pass_through_days) / len(all_active_days)
                if all_active_days
                else 0.0
            )

            # Balance volatility: std dev of balances
            balances = info["balances"]
            if len(balances) >= 2:
                mean_bal = sum(balances) / len(balances)
                variance = sum((b - mean_bal) ** 2 for b in balances) / len(balances)
                balance_volatility = round(variance**0.5, 2)
            else:
                balance_volatility = 0.0

            # Negative balance count
            negative_balance_count = sum(1 for b in balances if b < 0)

            # Debit/credit ratio (near 1.0 = pass-through behavior)
            debit_credit_ratio = (
                round(info["debit_volume"] / info["credit_volume"], 4)
                if info["credit_volume"] > 0
                else 0.0
            )

            # Max single txn ratio (layering: one big inflow then many small outflows)
            max_single_txn_ratio = (
                round(info["max_txn_amount"] / info["total_amount"], 4)
                if info["total_amount"] > 0
                else 0.0
            )

            # Generate a deterministic bank/city from ACID hash
            acc_hash = int(hashlib.md5(acid.encode()).hexdigest()[:8], 16)
            banks = ["IOB", "SBI", "HDFC", "ICICI", "PNB", "BOB"]
            cities = ["Chennai", "Mumbai", "Delhi", "Kolkata", "Hyderabad", "Bengaluru"]

            accounts.append(
                {
                    "account_id": acid,
                    "cif_id": info["cif_id"],
                    "role": "UNKNOWN",
                    "is_suspicious": False,
                    "is_fraud": False,
                    "bank": banks[acc_hash % len(banks)],
                    "city": cities[(acc_hash >> 4) % len(cities)],
                    "account_age_days": account_age_days,
                    "kyc_status": "VERIFIED",
                    "customer_age": info["customer_age"],
                    "balance": latest_balance,
                    "lien_amount": info["lien_amount"],
                    "debit_count": info["debit_count"],
                    "credit_count": info["credit_count"],
                    "debit_volume": round(info["debit_volume"], 2),
                    "credit_volume": round(info["credit_volume"], 2),
                    "avg_txn_amount": round(avg_amount, 2),
                    "avg_monthly_txn": avg_monthly_txn,
                    "upi_id": f"{acid[:8].lower()}@upi",
                    # CBS-specific derived features
                    "pass_through_ratio": round(pass_through_ratio, 4),
                    "balance_volatility": balance_volatility,
                    "negative_balance_count": negative_balance_count,
                    "debit_credit_ratio": debit_credit_ratio,
                    "max_single_txn_ratio": max_single_txn_ratio,
                }
            )

        return accounts

    def _detect_anomaly_flags(self, rows: List[Dict]) -> List[Dict]:
        """Flag suspicious patterns in the raw data as metadata for the pipeline."""
        flags: List[Dict] = []
        account_txns: Dict[str, List[Dict]] = defaultdict(list)

        for row in rows:
            acid = row.get("ACID", "").strip()
            if acid:
                account_txns[acid].append(row)

        for acid, txns in account_txns.items():
            # 1. Negative balances
            for txn in txns:
                balance = float(txn.get("balance", 0))
                if balance < 0:
                    flags.append(
                        {
                            "account_id": acid,
                            "flag": "NEGATIVE_BALANCE",
                            "detail": f"Balance {balance} after txn {txn.get('TRAN_ID', '')[:12]}",
                        }
                    )
                    break  # One flag per account

            # 2. Rapid small debits (smurfing): 3+ debits under 500 in the dataset
            small_debits = [
                t
                for t in txns
                if t.get("PART_TRAN_TYPE", "").strip() == "D"
                and float(t.get("TRAN_AMT", 0)) < 500
            ]
            if len(small_debits) >= 3:
                flags.append(
                    {
                        "account_id": acid,
                        "flag": "RAPID_SMALL_DEBITS",
                        "detail": f"{len(small_debits)} debits under 500",
                    }
                )

            # 3. Large credit followed by many small debits (layering)
            credits = [t for t in txns if t.get("PART_TRAN_TYPE", "").strip() == "C"]
            debits = [t for t in txns if t.get("PART_TRAN_TYPE", "").strip() == "D"]
            if credits and debits:
                max_credit = max(float(c.get("TRAN_AMT", 0)) for c in credits)
                small_debit_count = sum(
                    1 for d in debits if float(d.get("TRAN_AMT", 0)) < max_credit * 0.1
                )
                if max_credit > 10000 and small_debit_count >= 3:
                    flags.append(
                        {
                            "account_id": acid,
                            "flag": "LAYERING_PATTERN",
                            "detail": f"Credit {max_credit} followed by {small_debit_count} small debits",
                        }
                    )

            # 4. Young account + high volume
            acct_opn = txns[0].get("ACCT_OPN_DATE", "").strip()
            if acct_opn:
                try:
                    opn_date = self._parse_date(acct_opn)
                    latest = max(self._parse_date(t["TRAN_DATE"]) for t in txns)
                    age_days = (latest - opn_date).days
                    if age_days < 90 and len(txns) > 10:
                        flags.append(
                            {
                                "account_id": acid,
                                "flag": "YOUNG_ACCOUNT_HIGH_VOLUME",
                                "detail": f"Account age {age_days}d with {len(txns)} transactions",
                            }
                        )
                except (ValueError, TypeError):
                    pass

        return flags
