"""Tests for STR submission workflow lifecycle."""

import pytest
from repositories.str_repository import VALID_TRANSITIONS, STRRepository
from services.str_service import STRService


@pytest.fixture
def str_service():
    repo = STRRepository()
    return STRService(repo)


class TestSTRCreation:
    def test_create_str(self, str_service):
        result = str_service.create_str(
            alert_ids=["ALT_001"],
            account_ids=["ACC_001", "ACC_002"],
            narrative="Suspicious transfer pattern detected.",
        )
        assert result["str_id"].startswith("STR-")
        assert result["status"] == "DRAFT"
        assert result["alert_ids"] == ["ALT_001"]

    def test_list_strs(self, str_service):
        str_service.create_str(alert_ids=["A1"], account_ids=[], narrative="Test narrative 1.")
        str_service.create_str(alert_ids=["A2"], account_ids=[], narrative="Test narrative 2.")
        listing = str_service.list_strs()
        assert listing["total"] == 2
        assert len(listing["records"]) == 2


class TestSTRLifecycle:
    def test_full_lifecycle(self, str_service):
        # Create
        created = str_service.create_str(
            alert_ids=["ALT_001"],
            account_ids=["ACC_001"],
            narrative="Full lifecycle test narrative.",
        )
        str_id = created["str_id"]
        assert created["status"] == "DRAFT"

        # Approve
        approved = str_service.approve_for_submission(str_id, approved_by="supervisor_1")
        assert approved["status"] == "READY_FOR_SUBMISSION"
        assert approved["approved_by"] == "supervisor_1"

        # Submit
        submitted = str_service.submit(str_id)
        assert submitted["status"] == "SUBMITTED"
        assert submitted["fiu_reference"].startswith("FIU-")

        # Acknowledge
        acked = str_service.acknowledge(str_id)
        assert acked["status"] == "ACKNOWLEDGED"

    def test_invalid_transition_draft_to_submitted(self, str_service):
        created = str_service.create_str(
            alert_ids=["A1"],
            account_ids=[],
            narrative="Invalid transition test.",
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            str_service.submit(created["str_id"])

    def test_invalid_transition_acknowledged_to_draft(self, str_service):
        created = str_service.create_str(
            alert_ids=["A1"],
            account_ids=[],
            narrative="Full cycle for invalid test.",
        )
        str_id = created["str_id"]
        str_service.approve_for_submission(str_id, "admin")
        str_service.submit(str_id)
        str_service.acknowledge(str_id)
        with pytest.raises(ValueError, match="Invalid status transition"):
            str_service.approve_for_submission(str_id, "admin")

    def test_get_str(self, str_service):
        created = str_service.create_str(
            alert_ids=["A1"],
            account_ids=[],
            narrative="Get test narrative content.",
        )
        result = str_service.get_str(created["str_id"])
        assert result is not None
        assert result["narrative"] == "Get test narrative content."

    def test_get_nonexistent_str(self, str_service):
        assert str_service.get_str("STR-NONEXISTENT") is None

    def test_list_by_status(self, str_service):
        str_service.create_str(alert_ids=["A1"], account_ids=[], narrative="Draft STR narrative.")
        created = str_service.create_str(alert_ids=["A2"], account_ids=[], narrative="Approved STR test.")
        str_service.approve_for_submission(created["str_id"], "admin")

        drafts = str_service.list_strs(status="DRAFT")
        assert drafts["total"] == 1
        ready = str_service.list_strs(status="READY_FOR_SUBMISSION")
        assert ready["total"] == 1


class TestSTRRepository:
    def test_valid_transitions(self):
        assert "READY_FOR_SUBMISSION" in VALID_TRANSITIONS["DRAFT"]
        assert "SUBMITTED" in VALID_TRANSITIONS["READY_FOR_SUBMISSION"]
        assert "ACKNOWLEDGED" in VALID_TRANSITIONS["SUBMITTED"]
        assert len(VALID_TRANSITIONS["ACKNOWLEDGED"]) == 0

    def test_count(self):
        repo = STRRepository()
        repo.create({"str_id": "S1", "status": "DRAFT"})
        repo.create({"str_id": "S2", "status": "DRAFT"})
        assert repo.count() == 2
        assert repo.count(status="DRAFT") == 2
