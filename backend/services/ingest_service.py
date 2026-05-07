"""
Ingest service — Kafka consumer status and stream demo.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List

from ingest.kafka_consumer import TransactionConsumer


class IngestService:
    """Business logic for ingestion status and demo streaming."""

    def __init__(self, kafka_consumer: TransactionConsumer, kafka_enabled: bool):
        self._consumer = kafka_consumer
        self._kafka_enabled = kafka_enabled

    def get_status(self) -> Dict:
        """Return Kafka consumer health and lag metrics."""
        return self._consumer.get_status()

    def get_stream_demo(self, count: int, dataset: Dict) -> Dict:
        """Simulated real-time transaction stream for demo visualization."""
        txns = dataset.get("transactions", [])
        if not txns:
            return {"transactions": [], "source": "demo"}

        sample = random.sample(txns, min(count, len(txns)))
        now = datetime.utcnow()
        stream = []
        for i, t in enumerate(sample):
            entry = dict(t)
            entry["timestamp"] = (
                now - timedelta(seconds=random.randint(0, 30))
            ).isoformat()
            entry["stream_offset"] = i
            stream.append(entry)

        return {
            "transactions": stream,
            "source": "kafka" if self._kafka_enabled else "demo-simulation",
            "topic": self._consumer.topic,
            "timestamp": now.isoformat(),
        }
