"""
Download PaySim dataset from Kaggle.

Usage:
    python scripts/download_paysim.py

Prerequisites:
    pip install kaggle
    Configure ~/.kaggle/kaggle.json with your API key.

Downloads to: data/paysim/
"""

import os
import sys
import subprocess
import zipfile
import csv


DATASET = "ntnu-testimon/paysim1"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "paysim")
EXPECTED_COLUMNS = {"step", "type", "amount", "nameOrig", "nameDest", "isFraud"}


def download():
    """Download PaySim dataset via Kaggle CLI."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Downloading PaySim dataset to {OUTPUT_DIR}...")
    try:
        subprocess.run(
            [
                "kaggle", "datasets", "download",
                "-d", DATASET,
                "-p", OUTPUT_DIR,
                "--unzip",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print("Download complete.")
    except FileNotFoundError:
        print("ERROR: kaggle CLI not found. Install with: pip install kaggle")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: Download failed: {exc.stderr}")
        sys.exit(1)


def validate():
    """Validate the downloaded CSV structure."""
    csv_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".csv")]
    if not csv_files:
        print("ERROR: No CSV files found in", OUTPUT_DIR)
        sys.exit(1)

    csv_path = os.path.join(OUTPUT_DIR, csv_files[0])
    print(f"Validating: {csv_path}")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])

        missing = EXPECTED_COLUMNS - headers
        if missing:
            print(f"WARNING: Missing columns: {missing}")
        else:
            print("Schema validation passed.")

        # Count rows and fraud rate
        total = 0
        fraud = 0
        for row in reader:
            total += 1
            if int(row.get("isFraud", 0)) == 1:
                fraud += 1

    print(f"\nDataset statistics:")
    print(f"  Total transactions: {total:,}")
    print(f"  Fraudulent: {fraud:,} ({fraud/max(total,1)*100:.2f}%)")
    print(f"  Legitimate: {total - fraud:,}")
    print(f"  CSV path: {csv_path}")


if __name__ == "__main__":
    download()
    validate()
