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
