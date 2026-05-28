"""
MuleCatch Kafka Consumer
=========================
Reads transaction messages from Kafka topics, parses them via CBS parser,
runs the detection pipeline, and stores new alerts.
"""

import json
import logging
import os
import time
import threading
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_UPI", "mulecatch.transactions")
KAFKA_GROUP = os.getenv("KAFKA_GROUP_ID", "mulecatch-detection-group")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "false").lower() in ("true", "1", "yes")


class TransactionConsumer:
    """Kafka consumer that processes transaction batches through the detection pipeline."""

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        topic: Optional[str] = None,
        group_id: Optional[str] = None,
        batch_size: int = 100,
        batch_timeout_ms: int = 5000,
    ):
        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP
        self.topic = topic or KAFKA_TOPIC
        self.group_id = group_id or KAFKA_GROUP
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms

        self._consumer = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = {
            "messages_consumed": 0,
            "batches_processed": 0,
            "alerts_generated": 0,
            "last_processed_at": None,
            "errors": 0,
            "status": "stopped",
        }

    def _create_consumer(self):
        try:
            from kafka import KafkaConsumer
            self._consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=self.batch_timeout_ms,
                max_poll_records=self.batch_size,
            )
            return True
        except Exception as exc:
            logger.error("Failed to create Kafka consumer: %s", exc)
            self._stats["status"] = f"error: {exc}"
            return False

    def start(self, pipeline=None, persistence=None):
        """Start consuming in a background thread."""
        if self._running:
            return

        if not self._create_consumer():
            return

        self._running = True
        self._stats["status"] = "running"
        self._thread = threading.Thread(
            target=self._consume_loop,
            args=(pipeline, persistence),
            daemon=True,
        )
        self._thread.start()
        logger.info("Kafka consumer started on topic '%s'", self.topic)

    def stop(self):
        self._running = False
        self._stats["status"] = "stopped"
        if self._consumer:
            self._consumer.close()
            self._consumer = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Kafka consumer stopped")

    def _consume_loop(self, pipeline, persistence):
        from ingest.cbs_parser import parse_cbs_log_line

        batch: List[Dict] = []

        while self._running:
            try:
                if self._consumer is None:
                    break

                # Poll for messages
                records = self._consumer.poll(timeout_ms=self.batch_timeout_ms)

                for topic_partition, messages in records.items():
                    for message in messages:
                        txn = message.value
                        if isinstance(txn, str):
                            txn = parse_cbs_log_line(txn)
                        if txn and txn.get("txn_id"):
                            batch.append(txn)
                            self._stats["messages_consumed"] += 1

                # Process batch when full or on timeout
                if batch and (len(batch) >= self.batch_size or not records):
                    self._process_batch(batch, pipeline, persistence)
                    # Manual commit after successful processing (at-least-once)
                    if self._consumer:
                        self._consumer.commit()
                    batch = []

            except Exception as exc:
                logger.error("Kafka consumer error: %s", exc)
                self._stats["errors"] += 1
                time.sleep(1)

    def _process_batch(self, transactions: List[Dict], pipeline, persistence):
        """Run detection on a batch of transactions."""
        try:
            if pipeline is None or persistence is None:
                logger.warning("Pipeline or persistence not available, skipping batch")
                return

            # We need account data — use what's in persistence or generate
            dataset = persistence.get_dataset()
            accounts = dataset["accounts"] if dataset else []

            if not accounts:
                logger.warning("No account data available for detection")
                return

            alerts = pipeline.run(transactions, accounts)
            if alerts:
                from services.detection_service import alert_to_dict
                alert_dicts = [alert_to_dict(a) for a in alerts]
                existing = persistence.get_alerts(limit=1000)
                persistence.store_alerts(existing + alert_dicts)
                self._stats["alerts_generated"] += len(alerts)

            self._stats["batches_processed"] += 1
            self._stats["last_processed_at"] = datetime.utcnow().isoformat()

        except Exception as exc:
            logger.error("Batch processing error: %s", exc)
            self._stats["errors"] += 1

    def get_status(self) -> Dict:
        return {
            **self._stats,
            "topic": self.topic,
            "group_id": self.group_id,
            "bootstrap_servers": self.bootstrap_servers,
            "kafka_enabled": KAFKA_ENABLED,
        }
