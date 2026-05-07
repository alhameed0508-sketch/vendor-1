"""
MuleCatch Graph Seeder
Loads synthetic dataset into Neo4j as a property graph.
Nodes: Account, Device, IPAddress
Edges: SENT_TO, USES_DEVICE, FROM_IP
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import GraphDatabase
from data.synthetic.generator import build_full_dataset


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "CHANGE_ME_NOT_FOR_PRODUCTION")


SCHEMA_QUERIES = [
    "CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.account_id IS UNIQUE",
    "CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.device_id IS UNIQUE",
    "CREATE CONSTRAINT ip_addr IF NOT EXISTS FOR (i:IPAddress) REQUIRE i.address IS UNIQUE",
    "CREATE CONSTRAINT txn_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.txn_id IS UNIQUE",
    "CREATE CONSTRAINT alert_id IF NOT EXISTS FOR (al:Alert) REQUIRE al.alert_id IS UNIQUE",
    "CREATE INDEX account_cluster IF NOT EXISTS FOR (a:Account) ON (a.cluster_id)",
    "CREATE INDEX txn_suspicious IF NOT EXISTS FOR (t:Transaction) ON (t.is_suspicious)",
    "CREATE INDEX account_role IF NOT EXISTS FOR (a:Account) ON (a.role)",
    "CREATE INDEX alert_severity IF NOT EXISTS FOR (al:Alert) ON (al.severity)",
    "CREATE INDEX alert_status IF NOT EXISTS FOR (al:Alert) ON (al.status)",
    "CREATE INDEX alert_risk_score IF NOT EXISTS FOR (al:Alert) ON (al.risk_score)",
]


def seed_graph(driver, dataset: dict):
    print("Creating schema constraints & indexes...")
    with driver.session() as session:
        for q in SCHEMA_QUERIES:
            session.run(q)

    print(f"Seeding {len(dataset['accounts'])} accounts...")
    with driver.session() as session:
        session.run("""
            UNWIND $accounts AS acc
            MERGE (a:Account {account_id: acc.account_id})
            SET a.upi_id       = acc.upi_id,
                a.bank         = acc.bank,
                a.city         = acc.city,
                a.role         = acc.role,
                a.high_risk    = acc.high_risk,
                a.account_age  = acc.account_age_days,
                a.kyc_status   = acc.kyc_status,
                a.cluster_id   = acc.cluster_id,
                a.avg_monthly  = acc.avg_monthly_txn
        """, accounts=dataset["accounts"])

    print(f"Seeding {len(dataset['transactions'])} transactions...")
    batch_size = 200
    txns = dataset["transactions"]
    for i in range(0, len(txns), batch_size):
        batch = txns[i:i + batch_size]
        with driver.session() as session:
            session.run("""
                UNWIND $txns AS t
                MATCH (src:Account {account_id: t.from_account})
                MATCH (dst:Account {account_id: t.to_account})
                MERGE (txn:Transaction {txn_id: t.txn_id})
                SET txn.amount        = t.amount,
                    txn.timestamp     = t.timestamp,
                    txn.txn_type      = t.txn_type,
                    txn.is_suspicious = t.is_suspicious,
                    txn.pattern       = t.pattern,
                    txn.cluster_id    = t.cluster_id,
                    txn.upi_id        = t.upi_id,
                    txn.ip_address    = t.ip_address,
                    txn.device_id     = t.device_id
                MERGE (src)-[:SENT_TO {
                    txn_id:    t.txn_id,
                    amount:    t.amount,
                    timestamp: t.timestamp,
                    pattern:   t.pattern
                }]->(dst)

                WITH txn, t
                MERGE (d:Device {device_id: t.device_id})
                MERGE (txn)-[:USES_DEVICE]->(d)

                WITH txn, t
                MERGE (ip:IPAddress {address: t.ip_address})
                MERGE (txn)-[:FROM_IP]->(ip)
            """, txns=batch)
        print(f"  Seeded batch {i // batch_size + 1}/{(len(txns) - 1) // batch_size + 1}")

    # Mark shared devices / IPs
    print("Linking shared device fingerprints...")
    with driver.session() as session:
        session.run("""
            MATCH (d:Device)<-[:USES_DEVICE]-(t:Transaction)
            WITH d, count(t) AS txn_count
            SET d.txn_count = txn_count,
                d.shared    = (txn_count > 3)
        """)
        session.run("""
            MATCH (ip:IPAddress)<-[:FROM_IP]-(t:Transaction)
            WITH ip, count(t) AS txn_count
            SET ip.txn_count = txn_count,
                ip.shared    = (txn_count > 3)
        """)

    # Cluster stats
    with driver.session() as session:
        result = session.run("""
            MATCH (a:Account)
            RETURN a.role AS role, count(*) AS cnt
            ORDER BY cnt DESC
        """)
        print("\nAccount breakdown:")
        for row in result:
            print(f"  {row['role']:12s}: {row['cnt']}")

        result = session.run("MATCH ()-[r:SENT_TO]->() RETURN count(r) AS cnt")
        print(f"  SENT_TO edges : {result.single()['cnt']}")


def main():
    print("MuleCatch Graph Seeder")
    print(f"Connecting to Neo4j at {NEO4J_URI}...")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        print("Connected.\n")

        dataset_path = Path(__file__).parent.parent / "data" / "synthetic" / "synthetic_dataset.json"
        if dataset_path.exists():
            print(f"Loading existing dataset: {dataset_path}")
            with open(dataset_path) as f:
                dataset = json.load(f)
        else:
            print("Generating fresh synthetic dataset...")
            dataset = build_full_dataset(num_clusters=5, num_legit_accounts=50)

        seed_graph(driver, dataset)
        print("\nSeeding complete.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()