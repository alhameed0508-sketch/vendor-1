"""
Dataset repository — wraps PersistenceLayer dataset cache.
"""

from typing import Dict, Optional

from graph_engine.persistence import PersistenceLayer


class DatasetRepository:
    """Data access for the synthetic/cached dataset."""

    def __init__(self, persistence: PersistenceLayer):
        self._persistence = persistence

    def get(self) -> Optional[Dict]:
        """Return the cached dataset or None."""
        return self._persistence.get_dataset()

    def set(self, dataset: Dict) -> None:
        """Cache a dataset."""
        self._persistence.set_dataset(dataset)

    def clear(self) -> None:
        """Clear cached alerts and dataset."""
        self._persistence.clear()
