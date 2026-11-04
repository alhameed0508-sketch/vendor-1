"""DetectionService.data_source: say whether the loaded dataset is generated or came from outside."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.detection_service import DetectionService


class FakeDatasets:
    def __init__(self, dataset):
        self._dataset = dataset

    def get(self):
        return self._dataset

    def set(self, dataset):
        self._dataset = dataset


def _service(dataset):
    return DetectionService(None, None, None, FakeDatasets(dataset), None)


@pytest.mark.parametrize(
    ("dataset", "expected"),
    [
        (None, "none"),
        ({"transactions": [], "accounts": [], "source": "synthetic"}, "synthetic"),
        ({"transactions": [], "accounts": []}, "loaded"),
    ],
)
def test_data_source(dataset, expected):
    assert _service(dataset).data_source() == expected


def test_generated_demo_dataset_is_marked_synthetic():
    service = _service(None)
    dataset = service.get_or_generate_dataset()
    assert dataset["source"] == "synthetic"
    assert service.data_source() == "synthetic"
