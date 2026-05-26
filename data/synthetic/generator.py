"""
MuleCatch Synthetic Data Generator
Generates realistic mule account clusters with UPI transaction patterns
for demo and testing purposes.
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json
import os

# ── seed for reproducibility ──────────────────────────────────────────────────
random.seed(42)

BANKS = ["IOB", "SBI", "HDFC", "ICICI", "PNB", "BOB", "UNION", "CANARA"]
CITIES = ["Chennai", "Mumbai", "Delhi", "Kolkata", "Hyderabad", "Pune", "Bengaluru"]
UPI_SUFFIXES = ["@okaxis", "@oksbi", "@okhdfcbank", "@ybl", "@upi", "@iob"]

# ── Cluster risk profiles for diverse demo data ──────────────────────────────
CLUSTER_PROFILES = [
    {
        "name": "aggressive_smurfing",
        "num_mules": 12,
        "account_age_max": 3,
        "kyc_bias": 0.1,          # 10% chance of VERIFIED (mostly PENDING)
        "device_share_rate": 0.9,
        "ip_share_rate": 0.8,
        "amount_range": (9500, 49500),
        "txns_per_mule": (4, 7),
        "num_aggregators": 1,
    },
    {
        "name": "high_value_consolidation",
        "num_mules": 10,
        "account_age_max": 5,
        "kyc_bias": 0.2,
        "device_share_rate": 0.85,
        "ip_share_rate": 0.7,
        "amount_range": (25000, 49900),
        "txns_per_mule": (3, 6),
        "num_aggregators": 2,
    },
    {
        "name": "medium_bot_pattern",
        "num_mules": 8,
        "account_age_max": 15,
        "kyc_bias": 0.4,
        "device_share_rate": 0.7,
        "ip_share_rate": 0.6,
        "amount_range": (5000, 35000),
        "txns_per_mule": (2, 4),
        "num_aggregators": 1,
    },
    {
        "name": "slow_layering",
        "num_mules": 6,
        "account_age_max": 30,
        "kyc_bias": 0.5,
        "device_share_rate": 0.5,
        "ip_share_rate": 0.4,
        "amount_range": (1000, 25000),
        "txns_per_mule": (2, 3),
        "num_aggregators": 1,
    },
    {
        "name": "new_account_burst",
        "num_mules": 14,
        "account_age_max": 2,
        "kyc_bias": 0.05,
        "device_share_rate": 0.95,
        "ip_share_rate": 0.9,
        "amount_range": (15000, 49000),
        "txns_per_mule": (5, 8),
        "num_aggregators": 1,
    },
]


def random_account() -> str:
    return f"AC{random.randint(10000000, 99999999)}"


def random_upi() -> str:
    prefix = "".join(random.choices("abcdefghijklmnop", k=6))
    return prefix + random.choice(UPI_SUFFIXES)


def random_ip() -> str:
    return f"192.168.{random.randint(1,50)}.{random.randint(1,254)}"


def random_device() -> str:
    return f"DEV_{uuid.uuid4().hex[:8].upper()}"


def make_timestamp(base: datetime, offset_minutes: int = 0, jitter: int = 10) -> str:
    ts = base + timedelta(minutes=offset_minutes + random.randint(0, jitter))
    return ts.isoformat()


# ── Mule Cluster Generator ────────────────────────────────────────────────────

class MuleClusterGenerator:
    """
    Generates a realistic mule network:
      - 1 source account (fraud origin)
      - 5-15 mule accounts (layering)
      - 1-2 aggregator accounts (consolidation)
      - Transactions following smurfing patterns
    """

    def __init__(self):
        self.accounts: List[Dict] = []
        self.transactions: List[Dict] = []
        self.devices: List[Dict] = []
        self.ips: List[str] = []
        self.cluster_id = f"CLU_{uuid.uuid4().hex[:8].upper()}"

    def generate(
        self,
        num_mules: int = 8,
        base_time: datetime = None,
        profile: Dict = None,
    ) -> Dict:
        if base_time is None:
            base_time = datetime.now() - timedelta(hours=random.randint(1, 72))

        # Use profile or defaults
        p = profile or {}
        account_age_max = p.get("account_age_max", 45)
        kyc_bias = p.get("kyc_bias", 0.5)
        device_share_rate = p.get("device_share_rate", 0.6)
        ip_share_rate = p.get("ip_share_rate", 0.5)
        amt_lo, amt_hi = p.get("amount_range", (499, 48999))
        txn_lo, txn_hi = p.get("txns_per_mule", (2, 5))
        n_agg = p.get("num_aggregators", random.randint(1, 2))

        # Source account (criminal origin) - always very new
        source = self._make_account(
            "SOURCE", high_risk=True,
            age_max=min(account_age_max, 5), kyc_bias=kyc_bias,
        )

        # Mule accounts (layering tier)
        mules = [
            self._make_account("MULE", age_max=account_age_max, kyc_bias=kyc_bias)
            for _ in range(num_mules)
        ]

        # Aggregator accounts (consolidation tier) - always new
        aggregators = [
            self._make_account(
                "AGGREGATOR", high_risk=True,
                age_max=min(account_age_max, 4), kyc_bias=kyc_bias,
            )
            for _ in range(n_agg)
        ]

        all_accounts = [source] + mules + aggregators
        self.accounts.extend(all_accounts)

        # Shared device/IP fingerprints (key detection signal)
        # Aggressive clusters share multiple devices/IPs
        num_shared_devices = max(1, int(device_share_rate * 4))
        num_shared_ips = max(1, int(ip_share_rate * 3))
        shared_devices = [random_device() for _ in range(num_shared_devices)]
        shared_ips = [random_ip() for _ in range(num_shared_ips)]
        for dev in shared_devices:
            self.devices.append({"device_id": dev, "type": "SHARED"})
        self.ips.extend(shared_ips)
        shared_device = shared_devices[0]
        shared_ip = shared_ips[0]

        # Phase 1: source -> mules (smurfing - many small txns)
        txn_time = base_time
        for mule in mules:
            n_txns = random.randint(txn_lo, txn_hi)
            for _ in range(n_txns):
                self.transactions.append({
                    "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
                    "from_account": source["account_id"],
                    "to_account": mule["account_id"],
                    "amount": round(random.uniform(amt_lo, amt_hi), 2),
                    "timestamp": make_timestamp(txn_time),
                    "upi_id": random_upi(),
                    "device_id": random.choice(shared_devices) if random.random() < device_share_rate else random_device(),
                    "ip_address": random.choice(shared_ips) if random.random() < ip_share_rate else random_ip(),
                    "txn_type": "UPI_PUSH",
                    "cluster_id": self.cluster_id,
                    "is_suspicious": True,
                    "pattern": "SMURFING",
                })
                txn_time += timedelta(minutes=random.randint(1, 5))

        # Phase 2: mules -> aggregators (rapid consolidation)
        consolidation_window = base_time + timedelta(hours=2)
        for mule in mules:
            aggregator = random.choice(aggregators)
            self.transactions.append({
                "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
                "from_account": mule["account_id"],
                "to_account": aggregator["account_id"],
                "amount": round(random.uniform(amt_lo, amt_hi), 2),
                "timestamp": make_timestamp(consolidation_window, jitter=30),
                "upi_id": random_upi(),
                "device_id": random.choice(shared_devices) if random.random() < device_share_rate * 0.7 else random_device(),
                "ip_address": random.choice(shared_ips) if random.random() < ip_share_rate * 0.6 else random_ip(),
                "txn_type": "UPI_PUSH",
                "cluster_id": self.cluster_id,
                "is_suspicious": True,
                "pattern": "CONSOLIDATION",
            })

        return {
            "cluster_id": self.cluster_id,
            "source_account": source["account_id"],
            "mule_accounts": [m["account_id"] for m in mules],
            "aggregator_accounts": [a["account_id"] for a in aggregators],
            "total_transactions": len(self.transactions),
            "accounts": self.accounts,
            "transactions": self.transactions,
            "shared_devices": self.devices,
            "shared_ips": self.ips,
        }

    def _make_account(
        self, role: str, high_risk: bool = False,
        age_max: int = 45, kyc_bias: float = 0.5,
    ) -> Dict:
        return {
            "account_id": random_account(),
            "upi_id": random_upi(),
            "bank": random.choice(BANKS),
            "city": random.choice(CITIES),
            "role": role,
            "high_risk": high_risk,
            "account_age_days": random.randint(1, age_max),
            "kyc_status": "VERIFIED" if random.random() < kyc_bias else "PENDING",
            "avg_monthly_txn": random.randint(5, 50),
            "cluster_id": self.cluster_id,
        }


def generate_legitimate_accounts(n: int = 50) -> List[Dict]:
    """Generate normal accounts to create realistic noise"""
    accounts = []
    for _ in range(n):
        accounts.append({
            "account_id": random_account(),
            "upi_id": random_upi(),
            "bank": random.choice(BANKS),
            "city": random.choice(CITIES),
            "role": "LEGITIMATE",
            "high_risk": False,
            "account_age_days": random.randint(180, 3650),
            "kyc_status": "VERIFIED",
            "avg_monthly_txn": random.randint(50, 500),
            "cluster_id": None,
        })
    return accounts


def generate_legitimate_transactions(
    accounts: List[Dict], n: int = 200
) -> List[Dict]:
    """Normal transactions between legit accounts"""
    txns = []
    base = datetime.now() - timedelta(hours=24)
    for _ in range(n):
        src, dst = random.sample(accounts, 2)
        txns.append({
            "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
            "from_account": src["account_id"],
            "to_account": dst["account_id"],
            "amount": round(random.uniform(100, 49999), 2),
            "timestamp": make_timestamp(base, offset_minutes=random.randint(0, 1440)),
            "upi_id": random_upi(),
            "device_id": random_device(),
            "ip_address": random_ip(),
            "txn_type": "UPI_PUSH",
            "cluster_id": None,
            "is_suspicious": False,
            "pattern": "NORMAL",
        })
    return txns


def generate_adversarial_accounts(n: int = 30) -> Tuple[List[Dict], List[Dict]]:
    """
    Generate hard-to-classify legitimate accounts that mimic mule patterns.
    Returns (accounts, transactions) for adversarial legit accounts.
    Tests the pipeline's false positive rate on edge cases.
    """
    accounts = []
    transactions = []
    base_time = datetime.now() - timedelta(hours=36)

    per_type = max(1, n // 5)

    # Type 1: High-volume merchants — 50+ txns/day, multiple recipients, but LEGIT
    for i in range(per_type):
        acc_id = random_account()
        accounts.append({
            "account_id": acc_id,
            "upi_id": random_upi(),
            "bank": random.choice(BANKS),
            "city": random.choice(CITIES),
            "role": "LEGITIMATE",
            "high_risk": False,
            "account_age_days": random.randint(365, 2000),
            "kyc_status": "VERIFIED",
            "avg_monthly_txn": random.randint(200, 800),
            "cluster_id": None,
            "is_suspicious": False,
        })
        # Generate many outgoing transactions to different recipients
        for _ in range(random.randint(50, 80)):
            recipient = random_account()
            transactions.append({
                "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
                "from_account": acc_id,
                "to_account": recipient,
                "amount": round(random.uniform(500, 25000), 2),
                "timestamp": make_timestamp(base_time, offset_minutes=random.randint(0, 1440)),
                "upi_id": random_upi(),
                "device_id": random_device(),
                "ip_address": random_ip(),
                "txn_type": "UPI_PUSH",
                "cluster_id": None,
                "is_suspicious": False,
                "pattern": "NORMAL",
            })

    # Type 2: Seasonal reactivation — dormant 6+ months, then active burst, but LEGIT
    for i in range(per_type):
        acc_id = random_account()
        accounts.append({
            "account_id": acc_id,
            "upi_id": random_upi(),
            "bank": random.choice(BANKS),
            "city": random.choice(CITIES),
            "role": "LEGITIMATE",
            "high_risk": False,
            "account_age_days": random.randint(400, 1500),
            "kyc_status": "VERIFIED",
            "avg_monthly_txn": random.randint(1, 2),  # Low historical average
            "cluster_id": None,
            "is_suspicious": False,
        })
        # Burst of activity after dormancy
        for _ in range(random.randint(10, 20)):
            transactions.append({
                "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
                "from_account": acc_id,
                "to_account": random_account(),
                "amount": round(random.uniform(5000, 45000), 2),
                "timestamp": make_timestamp(base_time, offset_minutes=random.randint(0, 720)),
                "upi_id": random_upi(),
                "device_id": random_device(),
                "ip_address": random_ip(),
                "txn_type": "UPI_PUSH",
                "cluster_id": None,
                "is_suspicious": False,
                "pattern": "NORMAL",
            })

    # Type 3: Small business structuring — amounts near 50k but legit payroll/vendor
    for i in range(per_type):
        acc_id = random_account()
        accounts.append({
            "account_id": acc_id,
            "upi_id": random_upi(),
            "bank": random.choice(BANKS),
            "city": random.choice(CITIES),
            "role": "LEGITIMATE",
            "high_risk": False,
            "account_age_days": random.randint(180, 1000),
            "kyc_status": "VERIFIED",
            "avg_monthly_txn": random.randint(30, 100),
            "cluster_id": None,
            "is_suspicious": False,
        })
        # Amounts near 50k ceiling — looks like structuring but is payroll
        for _ in range(random.randint(5, 12)):
            transactions.append({
                "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
                "from_account": acc_id,
                "to_account": random_account(),
                "amount": round(random.uniform(42000, 49500), 2),
                "timestamp": make_timestamp(base_time, offset_minutes=random.randint(0, 1440)),
                "upi_id": random_upi(),
                "device_id": random_device(),
                "ip_address": random_ip(),
                "txn_type": "UPI_PUSH",
                "cluster_id": None,
                "is_suspicious": False,
                "pattern": "NORMAL",
            })

    # Type 4: Shared family devices — 2-3 accounts sharing a device legitimately
    shared_dev = random_device()
    shared_ip = random_ip()
    family_accounts = []
    for i in range(min(per_type, 3)):
        acc_id = random_account()
        family_accounts.append(acc_id)
        accounts.append({
            "account_id": acc_id,
            "upi_id": random_upi(),
            "bank": random.choice(BANKS),
            "city": random.choice(CITIES),
            "role": "LEGITIMATE",
            "high_risk": False,
            "account_age_days": random.randint(365, 2500),
            "kyc_status": "VERIFIED",
            "avg_monthly_txn": random.randint(20, 100),
            "cluster_id": None,
            "is_suspicious": False,
        })
        for _ in range(random.randint(8, 15)):
            transactions.append({
                "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
                "from_account": acc_id,
                "to_account": random_account(),
                "amount": round(random.uniform(200, 15000), 2),
                "timestamp": make_timestamp(base_time, offset_minutes=random.randint(0, 1440)),
                "upi_id": random_upi(),
                "device_id": shared_dev,  # Shared device
                "ip_address": shared_ip,  # Shared IP
                "txn_type": "UPI_PUSH",
                "cluster_id": None,
                "is_suspicious": False,
                "pattern": "NORMAL",
            })

    # Type 5: New accounts with high activity — students/gig workers
    for i in range(per_type):
        acc_id = random_account()
        accounts.append({
            "account_id": acc_id,
            "upi_id": random_upi(),
            "bank": random.choice(BANKS),
            "city": random.choice(CITIES),
            "role": "LEGITIMATE",
            "high_risk": False,
            "account_age_days": random.randint(1, 5),  # Very new
            "kyc_status": "VERIFIED",
            "avg_monthly_txn": random.randint(30, 80),
            "cluster_id": None,
            "is_suspicious": False,
        })
        for _ in range(random.randint(8, 20)):
            transactions.append({
                "txn_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
                "from_account": acc_id,
                "to_account": random_account(),
                "amount": round(random.uniform(100, 10000), 2),
                "timestamp": make_timestamp(base_time, offset_minutes=random.randint(0, 1440)),
                "upi_id": random_upi(),
                "device_id": random_device(),
                "ip_address": random_ip(),
                "txn_type": "UPI_PUSH",
                "cluster_id": None,
                "is_suspicious": False,
                "pattern": "NORMAL",
            })

    return accounts, transactions


def build_adversarial_dataset(
    num_clusters: int = 3,
    num_legit_accounts: int = 30,
    num_adversarial: int = 20,
) -> Dict:
    """
    Build a dataset mixing mule clusters, clean legit, and adversarial legit.
    The adversarial accounts are designed to be hard-to-classify edge cases.
    """
    all_accounts = []
    all_transactions = []
    clusters = []

    # Generate mule clusters (same as standard)
    base_time = datetime.now() - timedelta(hours=48)
    for i in range(num_clusters):
        profile = CLUSTER_PROFILES[i % len(CLUSTER_PROFILES)]
        gen = MuleClusterGenerator()
        cluster = gen.generate(
            num_mules=profile["num_mules"],
            base_time=base_time + timedelta(hours=i * 8),
            profile=profile,
        )
        clusters.append({k: v for k, v in cluster.items()
                         if k not in ("accounts", "transactions")})
        all_accounts.extend(cluster["accounts"])
        all_transactions.extend(cluster["transactions"])

    # Clean legitimate accounts
    legit_accounts = generate_legitimate_accounts(num_legit_accounts)
    legit_txns = generate_legitimate_transactions(legit_accounts, n=num_legit_accounts * 5)
    all_accounts.extend(legit_accounts)
    all_transactions.extend(legit_txns)

    # Adversarial legitimate accounts (hard edge cases)
    adv_accounts, adv_txns = generate_adversarial_accounts(num_adversarial)
    all_accounts.extend(adv_accounts)
    all_transactions.extend(adv_txns)

    random.shuffle(all_transactions)

    suspicious_count = sum(
        1 for a in all_accounts
        if a.get("role") in ("MULE", "SOURCE", "AGGREGATOR")
    )
    legit_count = len(all_accounts) - suspicious_count

    return {
        "generated_at": datetime.now().isoformat(),
        "clusters": clusters,
        "accounts": all_accounts,
        "transactions": all_transactions,
        "stats": {
            "total_accounts": len(all_accounts),
            "total_transactions": len(all_transactions),
            "suspicious_accounts": suspicious_count,
            "legitimate_accounts": legit_count,
            "adversarial_accounts": len(adv_accounts),
            "suspicious_transactions": sum(
                1 for t in all_transactions if t.get("is_suspicious")
            ),
            "mule_clusters": num_clusters,
        },
    }


def build_full_dataset(
    num_clusters: int = 5, num_legit_accounts: int = 50
) -> Dict:
    """Build the complete synthetic dataset for demo"""
    all_accounts = []
    all_transactions = []
    clusters = []

    # Generate mule clusters with varied risk profiles
    base_time = datetime.now() - timedelta(hours=48)
    for i in range(num_clusters):
        profile = CLUSTER_PROFILES[i % len(CLUSTER_PROFILES)]
        gen = MuleClusterGenerator()
        cluster = gen.generate(
            num_mules=profile["num_mules"],
            base_time=base_time + timedelta(hours=i * 8),
            profile=profile,
        )
        clusters.append({k: v for k, v in cluster.items()
                         if k not in ("accounts", "transactions")})
        all_accounts.extend(cluster["accounts"])
        all_transactions.extend(cluster["transactions"])

    # Generate legitimate data (noise)
    legit_accounts = generate_legitimate_accounts(num_legit_accounts)
    legit_txns = generate_legitimate_transactions(legit_accounts, n=200)
    all_accounts.extend(legit_accounts)
    all_transactions.extend(legit_txns)

    # Shuffle for realism
    random.shuffle(all_transactions)

    return {
        "generated_at": datetime.now().isoformat(),
        "clusters": clusters,
        "accounts": all_accounts,
        "transactions": all_transactions,
        "stats": {
            "total_accounts": len(all_accounts),
            "total_transactions": len(all_transactions),
            "suspicious_transactions": sum(
                1 for t in all_transactions if t.get("is_suspicious")
            ),
            "mule_clusters": num_clusters,
        },
    }


if __name__ == "__main__":
    print("Generating MuleCatch synthetic dataset...")
    dataset = build_full_dataset(num_clusters=5, num_legit_accounts=50)

    out_path = os.path.join(os.path.dirname(__file__), "synthetic_dataset.json")
    with open(out_path, "w") as f:
        json.dump(dataset, f, indent=2)

    stats = dataset["stats"]
    print(f"Dataset generated: {out_path}")
    print(f"  Accounts     : {stats['total_accounts']}")
    print(f"  Transactions : {stats['total_transactions']}")
    print(f"  Suspicious   : {stats['suspicious_transactions']}")
    print(f"  Mule clusters: {stats['mule_clusters']}")
