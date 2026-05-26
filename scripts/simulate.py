#!/usr/bin/env python3
"""
MuleCatch Simulation Script

Generates synthetic mule account data, runs the detection pipeline,
and pushes results to the backend API for frontend visualization.

Usage:
    python scripts/simulate.py                # default: 5 clusters, 50 legit accounts
    python scripts/simulate.py --clusters 8   # custom cluster count
    python scripts/simulate.py --standalone   # run pipeline without backend

Requires: backend running at http://localhost:8000 (unless --standalone)
"""

import argparse
import json
import sys
import os
import time

# Add project root to path so we can import backend modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, PROJECT_ROOT)


def run_via_api(base_url: str, clusters: int) -> None:
    """Trigger detection via the backend API (requires backend running)."""
    import httpx

    print(f"\n--- MuleCatch Simulation ---")
    print(f"Backend: {base_url}")
    print(f"Clusters: {clusters}\n")

    # Step 1: Check backend health
    print("[1/4] Checking backend health...")
    try:
        r = httpx.get(f"{base_url}/health", timeout=5)
        if r.status_code == 200:
            print("      Backend is running.")
        else:
            print(f"      WARNING: /health returned {r.status_code}")
    except httpx.ConnectError:
        print("      ERROR: Cannot connect to backend.")
        print(f"      Start the backend first: cd backend && uvicorn api.app:app --reload")
        sys.exit(1)

    # Step 2: Trigger fresh detection
    print("[2/4] Triggering detection pipeline...")
    try:
        r = httpx.post(f"{base_url}/api/v1/run-detection", timeout=30)
        if r.status_code == 200:
            print("      Detection pipeline triggered.")
        elif r.status_code == 401 or r.status_code == 403:
            # Auth may block — try fetching alerts directly (which auto-triggers)
            print("      Auth blocked /run-detection. Fetching alerts instead...")
        else:
            print(f"      Response: {r.status_code} — {r.text[:200]}")
    except Exception as e:
        print(f"      Note: {e}. Will try fetching alerts directly.")

    # Step 3: Wait for pipeline to complete
    print("[3/4] Waiting for pipeline to process...")
    time.sleep(2)

    # Step 4: Fetch and display alerts
    print("[4/4] Fetching alerts from backend...\n")
    try:
        r = httpx.get(f"{base_url}/api/v1/alerts?limit=50", timeout=15)
        body = r.json()
        data = body.get("data", body)
        alerts = data.get("alerts", [])

        if not alerts:
            print("      No alerts found. The pipeline may still be running.")
            print("      Try again in a few seconds, or refresh the frontend.")
            return

        print(f"{'ID':<18} {'Severity':<10} {'Risk':>6} {'Accts':>6} {'Txns':>6} {'Amount':>12} {'Status':<15}")
        print("-" * 80)

        for a in alerts:
            amount = f"₹{a['total_amount']:,.0f}"
            risk = f"{a['risk_score']*100:.0f}%"
            print(f"{a['alert_id']:<18} {a['severity']:<10} {risk:>6} {a['account_count']:>6} {a['txn_count']:>6} {amount:>12} {a['status']:<15}")

        print(f"\n--- Summary ---")
        print(f"Total alerts:  {len(alerts)}")
        print(f"Critical:      {sum(1 for a in alerts if a['severity'] == 'CRITICAL')}")
        print(f"High:          {sum(1 for a in alerts if a['severity'] == 'HIGH')}")
        print(f"Medium:        {sum(1 for a in alerts if a['severity'] == 'MEDIUM')}")
        total_amount = sum(a["total_amount"] for a in alerts)
        print(f"Total amount:  ₹{total_amount:,.0f} ({total_amount/100000:.1f}L)")
        print(f"\nOpen the frontend at http://localhost:3000 to visualize.\n")

    except Exception as e:
        print(f"      Error fetching alerts: {e}")


def run_standalone(clusters: int, legit_accounts: int) -> None:
    """Run the pipeline directly without a backend server."""
    print(f"\n--- MuleCatch Standalone Simulation ---")
    print(f"Clusters: {clusters}, Legit accounts: {legit_accounts}\n")

    # Step 1: Generate synthetic data
    print("[1/3] Generating synthetic transaction data...")
    from data.synthetic.generator import build_full_dataset

    dataset = build_full_dataset(
        num_clusters=clusters,
        num_legit_accounts=legit_accounts,
    )
    stats = dataset["stats"]
    print(f"      Accounts:     {stats['total_accounts']}")
    print(f"      Transactions: {stats['total_transactions']}")
    print(f"      Suspicious:   {stats['suspicious_transactions']}")
    print(f"      Clusters:     {stats['mule_clusters']}")

    # Step 2: Run detection pipeline
    print("\n[2/3] Running detection pipeline...")
    from detection.pipeline import DetectionPipeline

    pipeline = DetectionPipeline()
    alerts = pipeline.run(dataset["transactions"], dataset["accounts"])
    print(f"      Detected {len(alerts)} alert clusters.")

    # Step 3: Display results
    print(f"\n[3/3] Results:\n")
    print(f"{'ID':<18} {'Severity':<10} {'Risk':>6} {'Accts':>6} {'Txns':>6} {'Reason Codes'}")
    print("-" * 75)

    for a in sorted(alerts, key=lambda x: -x.risk_score):
        risk = f"{a.risk_score*100:.0f}%"
        codes = ", ".join(rc.split(":")[0] for rc in a.reason_codes[:3])
        print(f"{a.alert_id:<18} {a.severity:<10} {risk:>6} {a.account_count:>6} {a.txn_count:>6} {codes}")

    print(f"\n--- Summary ---")
    print(f"Total alerts:  {len(alerts)}")
    print(f"Critical:      {sum(1 for a in alerts if a.severity == 'CRITICAL')}")
    print(f"High:          {sum(1 for a in alerts if a.severity == 'HIGH')}")
    print(f"Medium:        {sum(1 for a in alerts if a.severity == 'MEDIUM')}")
    total = sum(a.total_amount for a in alerts)
    print(f"Total amount:  ₹{total:,.0f} ({total/100000:.1f}L)")

    # Save results to JSON
    out_path = os.path.join(PROJECT_ROOT, "data", "simulation_results.json")
    results = {
        "dataset_stats": stats,
        "alerts": [
            {
                "alert_id": a.alert_id,
                "severity": a.severity,
                "risk_score": a.risk_score,
                "confidence": a.confidence,
                "account_count": a.account_count,
                "txn_count": a.txn_count,
                "total_amount": a.total_amount,
                "reason_codes": a.reason_codes,
            }
            for a in alerts
        ],
    }
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {out_path}\n")


def main():
    parser = argparse.ArgumentParser(
        description="MuleCatch simulation — generate data, run detection, display results"
    )
    parser.add_argument(
        "--clusters", type=int, default=5,
        help="Number of mule clusters to generate (default: 5)",
    )
    parser.add_argument(
        "--legit", type=int, default=50,
        help="Number of legitimate accounts (default: 50)",
    )
    parser.add_argument(
        "--backend", type=str, default="http://localhost:8000",
        help="Backend URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--standalone", action="store_true",
        help="Run pipeline directly without backend server",
    )

    args = parser.parse_args()

    if args.standalone:
        run_standalone(args.clusters, args.legit)
    else:
        run_via_api(args.backend, args.clusters)


if __name__ == "__main__":
    main()
