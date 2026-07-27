"""
MuleCatch Kafka Producer
=========================
Seeds test transactions into Kafka for development and testing.
Uses the synthetic data generator to produce realistic transaction streams.
"""

import json
import logging
import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_UPI", "mulecatch.transactions")


class TransactionProducer:
    """Kafka producer for seeding test transactions."""

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        topic: Optional[str] = None,
    ):
        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP
        self.topic = topic or KAFKA_TOPIC
        self._producer = None

    def _create_producer(self):
        from kafka import KafkaProducer

        self._producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

    def send(self, transaction: dict):
        if self._producer is None:
            self._create_producer()
        try:
            self._producer.send(self.topic, value=transaction)
        except Exception as exc:
            logger.error("Failed to send message to Kafka: %s", exc)
            raise

    def flush(self):
        if self._producer:
            self._producer.flush()

    def close(self):
        if self._producer:
            self._producer.close()

    def seed_synthetic(
        self,
        num_clusters: int = 3,
        num_legit: int = 20,
        delay_ms: int = 50,
        dataset_repo=None,
    ):
        """Generate and send synthetic transactions to Kafka.

        If dataset_repo is provided, the generated dataset is cached so
        the consumer has account data available for detection.
        """
        from data.synthetic.generator import build_full_dataset

        print(
            f"Generating synthetic dataset ({num_clusters} clusters, {num_legit} legit accounts)..."
        )
        dataset = build_full_dataset(
            num_clusters=num_clusters, num_legit_accounts=num_legit
        )

        # Cache dataset so consumer can look up accounts during detection
        if dataset_repo is not None:
            dataset_repo.set(dataset)

        print(
            f"Sending {len(dataset['transactions'])} transactions to Kafka topic '{self.topic}'..."
        )
        for i, txn in enumerate(dataset["transactions"]):
            self.send(txn)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            if (i + 1) % 50 == 0:
                print(f"  Sent {i + 1}/{len(dataset['transactions'])} transactions")

        self.flush()
        print(
            f"Done. Sent {len(dataset['transactions'])} transactions to '{self.topic}'."
        )
        return len(dataset["transactions"])


if __name__ == "__main__":
    producer = TransactionProducer()
    try:
        count = producer.seed_synthetic(num_clusters=3, num_legit=20, delay_ms=10)
        print(f"\nSeeded {count} transactions successfully.")
    finally:
        producer.close()
