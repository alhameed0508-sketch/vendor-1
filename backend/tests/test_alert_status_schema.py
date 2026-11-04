import pytest
from api.v1.schemas.alerts import AlertUpdateRequest
from pydantic import ValidationError


def test_str_filed_accepted():
    assert AlertUpdateRequest(status="STR_FILED").status == "STR_FILED"


def test_unknown_status_rejected():
    with pytest.raises(ValidationError):
        AlertUpdateRequest(status="ESCALATED")


@pytest.mark.parametrize("status", ["OPEN", "UNDER_REVIEW", "RESOLVED", "FALSE_POSITIVE"])
def test_existing_statuses_still_accepted(status):
    assert AlertUpdateRequest(status=status).status == status


DISPOSITIONS = ["NO_FURTHER_ACTION", "SUSPICION_CONFIRMED_ESCALATED"]


@pytest.mark.parametrize("status", DISPOSITIONS)
def test_disposition_accepted_with_reason(status):
    req = AlertUpdateRequest(status=status, investigator_notes="Salary credits match employer records")
    assert req.status == status


@pytest.mark.parametrize("status", DISPOSITIONS)
@pytest.mark.parametrize("notes", [None, "", "   "])
def test_disposition_requires_a_reason(status, notes):
    with pytest.raises(ValidationError):
        AlertUpdateRequest(status=status, investigator_notes=notes)
