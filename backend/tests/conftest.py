"""
Shared test fixtures for MuleCatch test suite.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Tests must never attach to a developer's running Compose services. Pin all
# optional infrastructure before application modules and cached settings load.
os.environ["ENV"] = "development"
os.environ["AUTH_ENABLED"] = "false"
os.environ["KAFKA_ENABLED"] = "false"
os.environ["POSTGRES_URL"] = ""
os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/15"
os.environ["NEO4J_URI"] = "bolt://127.0.0.1:7699"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-with-at-least-32-bytes"

import pytest
from data.synthetic.generator import build_full_dataset
from detection.pipeline import DetectionPipeline
from genai.base import LLMProvider, LLMResponse, TemplateProvider


# ── Test isolation for feedback store ────────────────────────────────────────
# Redirect feedback writes to a temp file so tests never pollute the
# production feedback_log.jsonl.


@pytest.fixture(autouse=True, scope="session")
def _isolate_feedback_store():
    """Patch the default feedback store path to a temp file for all tests."""
    import models.active_learning.feedback_loop as fl_module

    original_path = fl_module.DEFAULT_FEEDBACK_STORE_PATH
    tmp = tempfile.NamedTemporaryFile(
        suffix="_test_feedback.jsonl",
        delete=False,
        mode="w",
    )
    tmp.close()

    fl_module.DEFAULT_FEEDBACK_STORE_PATH = type(original_path)(tmp.name)

    # Clear lru_cache singletons in deps so they pick up the new path.
    # get_detection_service also holds a FeedbackStore reference.
    try:
        from api import deps

        for fn in (
            deps.get_feedback_store,
            deps.get_feedback_engine,
            deps.get_feedback_service,
            deps.get_detection_service,
        ):
            fn.cache_clear()
    except (ImportError, AttributeError):
        pass

    yield

    # Restore and clean up
    fl_module.DEFAULT_FEEDBACK_STORE_PATH = original_path
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing — returns canned responses."""

    def __init__(self, response_text: str = "Mock LLM response"):
        self._response_text = response_text

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(
        self,
        messages,
        *,
        temperature=0.3,
        max_tokens=2048,
        timeout_seconds=30.0,
    ) -> LLMResponse:
        return LLMResponse(
            content=self._response_text,
            model="mock-model",
            provider="mock",
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=5.0,
        )


class FailingLLMProvider(LLMProvider):
    """Mock LLM provider that always raises an exception."""

    @property
    def provider_name(self) -> str:
        return "failing"

    def generate(self, messages, **kwargs) -> LLMResponse:
        raise RuntimeError("LLM provider unavailable")


@pytest.fixture(scope="module")
def small_dataset():
    """Small synthetic dataset with 2 mule clusters."""
    return build_full_dataset(num_clusters=2, num_legit_accounts=20)


@pytest.fixture(scope="module")
def pipeline():
    """Shared detection pipeline instance."""
    return DetectionPipeline()


@pytest.fixture
def mock_provider():
    """Mock LLM provider with a structured forensic response."""
    return MockLLMProvider(
        response_text=(
            "## Executive Brief\n"
            "This is a critical mule network alert.\n\n"
            "## Detailed Narrative\n"
            "The four-layer detection pipeline identified suspicious activity.\n\n"
            "## Regulatory Summary\n"
            "Per PMLA 2002, this warrants immediate STR filing.\n\n"
            "## Key Findings\n"
            "- Multiple shared devices detected\n"
            "- Accounts less than 7 days old\n"
            "- Structuring below 50k threshold\n\n"
            "## Recommended Actions\n"
            "- Freeze source accounts immediately\n"
            "- File STR with FIU-IND\n"
            "- Escalate to compliance officer\n"
        )
    )


@pytest.fixture
def template_provider():
    """Template fallback provider."""
    return TemplateProvider()


@pytest.fixture
def failing_provider():
    """LLM provider that always fails."""
    return FailingLLMProvider()


@pytest.fixture
def sample_alert_data():
    """Sample alert data dict for testing GenAI analysis."""
    return {
        "alert_id": "ALT_TEST12345",
        "severity": "CRITICAL",
        "risk_score": 0.85,
        "confidence": 0.90,
        "total_amount": 1250000.0,
        "txn_count": 42,
        "account_count": 8,
        "gnn_score": 0.78,
        "shared_devices": ["DEV_ABC123", "DEV_DEF456"],
        "shared_ips": ["192.168.1.100"],
        "reason_codes": [
            "R01: Account age < 7 days",
            "R04: Amounts structured below 50k threshold",
            "R06: Same-day credit-debit (pass-through)",
        ],
        "nodes": [
            {
                "account_id": "AC10000001",
                "role": "SOURCE",
                "smurf_score": 0.92,
                "bank": "IOB",
                "city": "Chennai",
                "account_age_days": 3,
                "kyc_status": "PENDING",
            },
            {
                "account_id": "AC10000002",
                "role": "MULE",
                "smurf_score": 0.75,
                "bank": "SBI",
                "city": "Mumbai",
                "account_age_days": 5,
                "kyc_status": "PENDING",
            },
            {
                "account_id": "AC10000003",
                "role": "AGGREGATOR",
                "smurf_score": 0.68,
                "bank": "HDFC",
                "city": "Delhi",
                "account_age_days": 2,
                "kyc_status": "VERIFIED",
            },
        ],
        "edges": [
            {
                "from_account": "AC10000001",
                "to_account": "AC10000002",
                "total_amount": 450000.0,
                "txn_count": 15,
                "pattern": "SMURFING",
            },
            {
                "from_account": "AC10000002",
                "to_account": "AC10000003",
                "total_amount": 430000.0,
                "txn_count": 12,
                "pattern": "CONSOLIDATION",
            },
        ],
    }


@pytest.fixture
def sample_onboarding_assessment():
    """Sample onboarding assessment result for testing."""
    return {
        "assessment_id": "OB_TEST001",
        "account_id": "AC999",
        "risk_score": 0.72,
        "risk_level": "HIGH",
        "recommendation": "BLOCK — high mule risk indicators detected",
        "reason_codes": [
            "Device shared with 2 other accounts",
            "KYC completeness below threshold (0.40)",
            "Account opened during off-hours (02:00)",
        ],
        "signals": [
            {"signal": "device_overlap", "score": 0.8, "weight": 12, "weighted": 0.096},
            {
                "signal": "kyc_completeness",
                "score": 0.6,
                "weight": 10,
                "weighted": 0.060,
            },
            {
                "signal": "application_hour",
                "score": 0.7,
                "weight": 5,
                "weighted": 0.035,
            },
        ],
        "assessed_at": "2025-05-08T10:00:00",
    }
