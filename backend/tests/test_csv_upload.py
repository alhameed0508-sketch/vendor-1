"""
Tests for Mule CSV adapter and CSV upload endpoints.

Unit tests: MuleCSVAdapter parsing, mapping, anomaly detection
Integration tests: POST /csv-upload/upload, GET /csv-upload/preview

Run: python -m pytest backend/tests/test_csv_upload.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from data_adapters.mule_csv_adapter import MuleCSVAdapter


# ── Fixtures ─────────────────────────────────────────────────────────────────


SAMPLE_CSV = """\
TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age
19/05/2026 18:30|txn_001|T|CI|D|ACCT_A|4|-96|UPI|CIF_1|22/11/2021 18:30|0|22
19/05/2026 18:30|txn_002|T|CI|C|ACCT_A|17500|17350|UPI|CIF_1|22/11/2021 18:30|0|22
19/05/2026 18:30|txn_003|T|CI|D|ACCT_A|25|-78|UPI|CIF_1|22/11/2021 18:30|0|22
19/05/2026 18:30|txn_004|T|CI|D|ACCT_A|14|-92|UPI|CIF_1|22/11/2021 18:30|0|22
19/05/2026 18:30|txn_005|T|CI|D|ACCT_A|40|-150|MB|CIF_1|22/11/2021 18:30|0|22
19/05/2026 18:30|txn_006|T|CI|C|ACCT_B|100000|130215.89|UPI|CIF_2|26/12/2022 18:30|0|22
19/05/2026 18:30|txn_007|T|CI|D|ACCT_B|25000|105215.89|MB|CIF_2|26/12/2022 18:30|0|22
19/05/2026 18:30|txn_008|T|CI|D|ACCT_B|25000|80215.89|IMPS_other|CIF_2|26/12/2022 18:30|0|22
19/05/2026 18:30|txn_009|T|CI|D|ACCT_B|25000|55215.89|NEFT|CIF_2|26/12/2022 18:30|0|22
19/05/2026 18:30|txn_010|T|CI|C|ACCT_C|500|3500|UPI|CIF_3|09/08/2023 18:30|8|30"""


SMURFING_CSV = """\
TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age
19/05/2026 18:30|s_001|T|CI|C|ACCT_S|50000|50000|UPI|CIF_S|01/04/2026 18:30|0|25
19/05/2026 18:30|s_002|T|CI|D|ACCT_S|100|49900|UPI|CIF_S|01/04/2026 18:30|0|25
19/05/2026 18:30|s_003|T|CI|D|ACCT_S|200|49700|UPI|CIF_S|01/04/2026 18:30|0|25
19/05/2026 18:30|s_004|T|CI|D|ACCT_S|150|49550|UPI|CIF_S|01/04/2026 18:30|0|25
19/05/2026 18:30|s_005|T|CI|D|ACCT_S|300|49250|UPI|CIF_S|01/04/2026 18:30|0|25
19/05/2026 18:30|s_006|T|CI|D|ACCT_S|50|49200|UPI|CIF_S|01/04/2026 18:30|0|25"""


@pytest.fixture
def adapter():
    return MuleCSVAdapter()


# ── Unit Tests: MuleCSVAdapter ───────────────────────────────────────────────


class TestMuleCSVAdapterParsing:
    """Tests for basic CSV parsing functionality."""

    def test_parse_returns_expected_keys(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        assert "transactions" in result
        assert "accounts" in result
        assert "anomaly_flags" in result

    def test_parse_transaction_count(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        assert len(result["transactions"]) == 10

    def test_parse_account_count(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        assert len(result["accounts"]) == 3  # ACCT_A, ACCT_B, ACCT_C

    def test_parse_max_rows_limits_output(self, adapter):
        result = adapter.parse(SAMPLE_CSV, max_rows=5)
        assert len(result["transactions"]) == 5

    def test_parse_empty_content(self, adapter):
        header_only = "TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age"
        result = adapter.parse(header_only)
        assert len(result["transactions"]) == 0
        assert len(result["accounts"]) == 0


class TestMuleCSVAdapterTransactionMapping:
    """Tests for CBS → MuleCatch transaction field mapping."""

    def test_debit_maps_acid_to_from_account(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        # txn_001 is PART_TRAN_TYPE=D, ACID=ACCT_A
        debit_txn = result["transactions"][0]
        assert debit_txn["from_account"] == "ACCT_A"
        assert debit_txn["to_account"].startswith("EXT_")

    def test_credit_maps_acid_to_to_account(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        # txn_002 is PART_TRAN_TYPE=C, ACID=ACCT_A
        credit_txn = result["transactions"][1]
        assert credit_txn["to_account"] == "ACCT_A"
        assert credit_txn["from_account"].startswith("EXT_")

    def test_amount_parsed_correctly(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        assert result["transactions"][0]["amount"] == 4.0
        assert result["transactions"][1]["amount"] == 17500.0

    def test_timestamp_iso_format(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        ts = result["transactions"][0]["timestamp"]
        assert ts == "2026-05-19T18:30:00"

    def test_channel_to_txn_type_upi(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        assert result["transactions"][0]["txn_type"] == "UPI_PUSH"

    def test_channel_to_txn_type_mb(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        # txn_005 has channel=MB
        mb_txn = result["transactions"][4]
        assert mb_txn["txn_type"] == "MOBILE_BANKING"

    def test_channel_to_txn_type_imps(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        # txn_008 has channel=IMPS_other
        imps_txn = result["transactions"][7]
        assert imps_txn["txn_type"] == "IMPS"

    def test_channel_to_txn_type_neft(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        # txn_009 has channel=NEFT
        neft_txn = result["transactions"][8]
        assert neft_txn["txn_type"] == "NEFT"

    def test_is_suspicious_defaults_false(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        for txn in result["transactions"]:
            assert txn["is_suspicious"] is False

    def test_pattern_defaults_normal(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        for txn in result["transactions"]:
            assert txn["pattern"] == "NORMAL"

    def test_balance_after_preserved(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        assert result["transactions"][0]["balance_after"] == -96.0
        assert result["transactions"][1]["balance_after"] == 17350.0


class TestMuleCSVAdapterAccountDerivation:
    """Tests for account derivation from transaction rows."""

    def test_account_id_matches_acid(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        account_ids = {a["account_id"] for a in result["accounts"]}
        assert "ACCT_A" in account_ids
        assert "ACCT_B" in account_ids
        assert "ACCT_C" in account_ids

    def test_cif_id_mapped(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        assert acct_a["cif_id"] == "CIF_1"

    def test_debit_credit_counts(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        assert acct_a["debit_count"] == 4  # txn_001, txn_003, txn_004, txn_005
        assert acct_a["credit_count"] == 1  # txn_002

    def test_account_age_days_calculated(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        # Opened 22/11/2021, latest txn 19/05/2026 = ~1639 days
        assert acct_a["account_age_days"] > 1600

    def test_customer_age_from_csv(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        assert acct_a["customer_age"] == 22

    def test_kyc_status_verified(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        for acct in result["accounts"]:
            assert acct["kyc_status"] == "VERIFIED"

    def test_role_defaults_unknown(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        for acct in result["accounts"]:
            assert acct["role"] == "UNKNOWN"

    def test_lien_amount_captured(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_c = next(a for a in result["accounts"] if a["account_id"] == "ACCT_C")
        assert acct_c["lien_amount"] == 8.0

    def test_balance_is_last_seen(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        # Last txn for ACCT_A is txn_005 with balance=-150
        assert acct_a["balance"] == -150.0


class TestMuleCSVAdapterAnomalyFlags:
    """Tests for pre-processing anomaly detection."""

    def test_negative_balance_flagged(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        neg_flags = [f for f in result["anomaly_flags"] if f["flag"] == "NEGATIVE_BALANCE"]
        # ACCT_A has negative balances
        flagged_accounts = {f["account_id"] for f in neg_flags}
        assert "ACCT_A" in flagged_accounts

    def test_rapid_small_debits_flagged(self, adapter):
        result = adapter.parse(SMURFING_CSV)
        smurf_flags = [f for f in result["anomaly_flags"] if f["flag"] == "RAPID_SMALL_DEBITS"]
        assert len(smurf_flags) >= 1
        assert smurf_flags[0]["account_id"] == "ACCT_S"

    def test_layering_pattern_flagged(self, adapter):
        result = adapter.parse(SMURFING_CSV)
        layer_flags = [f for f in result["anomaly_flags"] if f["flag"] == "LAYERING_PATTERN"]
        assert len(layer_flags) >= 1
        assert layer_flags[0]["account_id"] == "ACCT_S"

    def test_young_account_high_volume_flagged(self, adapter):
        # Build CSV with young account (< 90 days) and > 10 transactions
        lines = [
            "TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age"
        ]
        for i in range(12):
            lines.append(
                f"19/05/2026 18:30|young_{i}|T|CI|D|ACCT_YOUNG|100|{1000 - i * 100}|UPI|CIF_Y|01/05/2026 18:30|0|20"
            )
        csv_content = "\n".join(lines)
        result = adapter.parse(csv_content)
        young_flags = [f for f in result["anomaly_flags"] if f["flag"] == "YOUNG_ACCOUNT_HIGH_VOLUME"]
        assert len(young_flags) >= 1

    def test_no_false_positive_flags_on_clean_data(self, adapter):
        clean_csv = """\
TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age
19/05/2026 18:30|clean_001|T|CI|C|ACCT_CLEAN|5000|15000|UPI|CIF_CLEAN|01/01/2020 18:30|0|35
19/05/2026 18:30|clean_002|T|CI|D|ACCT_CLEAN|1000|14000|UPI|CIF_CLEAN|01/01/2020 18:30|0|35"""
        result = adapter.parse(clean_csv)
        assert len(result["anomaly_flags"]) == 0


class TestCounterpartyLinking:
    """Tests for TRAN_ID pairing and flow inference linking."""

    # Two accounts with shared TRAN_IDs — should produce internal links
    PAIRED_CSV = """\
TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age
19/05/2026 18:30|pair_001|T|CI|D|ACCT_X|5000|45000|UPI|CIF_X|01/01/2020 18:30|0|30
19/05/2026 18:30|pair_001|T|CI|C|ACCT_Y|5000|15000|UPI|CIF_Y|01/01/2020 18:30|0|28
19/05/2026 18:30|pair_002|T|CI|D|ACCT_Y|3000|12000|MB|CIF_Y|01/01/2020 18:30|0|28
19/05/2026 18:30|pair_002|T|CI|C|ACCT_Z|3000|8000|MB|CIF_Z|01/01/2020 18:30|0|25
19/05/2026 18:30|ext_003|T|CI|D|ACCT_X|1000|44000|UPI|CIF_X|01/01/2020 18:30|0|30"""

    def test_tran_id_pairing_creates_internal_links(self, adapter):
        result = adapter.parse(self.PAIRED_CSV)
        acc_ids = {a["account_id"] for a in result["accounts"]}
        internal = [
            t for t in result["transactions"]
            if t["from_account"] in acc_ids and t["to_account"] in acc_ids
        ]
        # pair_001: ACCT_X -> ACCT_Y, pair_002: ACCT_Y -> ACCT_Z
        assert len(internal) == 2
        assert internal[0]["from_account"] == "ACCT_X"
        assert internal[0]["to_account"] == "ACCT_Y"
        assert internal[0]["amount"] == 5000.0
        assert internal[1]["from_account"] == "ACCT_Y"
        assert internal[1]["to_account"] == "ACCT_Z"
        assert internal[1]["amount"] == 3000.0

    def test_unpaired_row_gets_ext_counterparty(self, adapter):
        result = adapter.parse(self.PAIRED_CSV)
        # ext_003 is unpaired D from ACCT_X
        ext_txns = [
            t for t in result["transactions"]
            if t["to_account"].startswith("EXT_")
        ]
        assert len(ext_txns) == 1
        assert ext_txns[0]["from_account"] == "ACCT_X"
        assert ext_txns[0]["amount"] == 1000.0

    def test_total_transaction_count_with_pairing(self, adapter):
        result = adapter.parse(self.PAIRED_CSV)
        # 5 raw rows, 2 pairs (4 rows -> 2 txns) + 1 single-leg = 3 txns
        assert len(result["transactions"]) == 3

    # All unique TRAN_IDs, matching D/C amounts — should trigger flow inference
    FLOW_CSV = """\
TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age
19/05/2026 18:30|flow_001|T|CI|D|ACCT_P|1000|9000|UPI|CIF_P|01/01/2020 18:30|0|30
19/05/2026 18:30|flow_002|T|CI|C|ACCT_Q|1000|6000|UPI|CIF_Q|01/01/2020 18:30|0|25
19/05/2026 18:30|flow_003|T|CI|D|ACCT_Q|500|5500|UPI|CIF_Q|01/01/2020 18:30|0|25
19/05/2026 18:30|flow_004|T|CI|C|ACCT_R|500|2500|UPI|CIF_R|01/01/2020 18:30|0|22"""

    def test_flow_inference_matches_amounts(self, adapter):
        result = adapter.parse(self.FLOW_CSV)
        acc_ids = {a["account_id"] for a in result["accounts"]}
        internal = [
            t for t in result["transactions"]
            if t["from_account"] in acc_ids and t["to_account"] in acc_ids
        ]
        # D(ACCT_P, 1000) matches C(ACCT_Q, 1000)
        # D(ACCT_Q, 500) matches C(ACCT_R, 500)
        assert len(internal) == 2

    def test_flow_inference_preserves_order(self, adapter):
        result = adapter.parse(self.FLOW_CSV)
        txns = result["transactions"]
        # Original order: flow_001 (D, matched), flow_002 (C, consumed),
        #                 flow_003 (D, matched), flow_004 (C, consumed)
        # Result: 2 internal link txns in order of debit rows
        assert len(txns) == 2
        assert txns[0]["from_account"] == "ACCT_P"
        assert txns[0]["to_account"] == "ACCT_Q"
        assert txns[1]["from_account"] == "ACCT_Q"
        assert txns[1]["to_account"] == "ACCT_R"


class TestCBSFeatures:
    """Tests for CBS-specific derived features."""

    def test_avg_monthly_txn_is_not_total_count(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        # ACCT_A has 5 txns, opened 2021, latest 2026 (~54 months)
        # avg_monthly_txn should be ~0.09, NOT 5
        assert acct_a["avg_monthly_txn"] < 5
        assert acct_a["avg_monthly_txn"] > 0

    def test_pass_through_ratio_computed(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        # ACCT_A has both D and C on same day → pass_through_ratio > 0
        assert "pass_through_ratio" in acct_a
        assert acct_a["pass_through_ratio"] == 1.0  # All on same day

    def test_balance_volatility_computed(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        assert "balance_volatility" in acct_a
        # ACCT_A balances: -96, 17350, -78, -92, -150 → high volatility
        assert acct_a["balance_volatility"] > 0

    def test_negative_balance_count(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_a = next(a for a in result["accounts"] if a["account_id"] == "ACCT_A")
        assert "negative_balance_count" in acct_a
        # Balances -96, 17350, -78, -92, -150 → 4 negative
        assert acct_a["negative_balance_count"] == 4

    def test_debit_credit_ratio(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_b = next(a for a in result["accounts"] if a["account_id"] == "ACCT_B")
        assert "debit_credit_ratio" in acct_b
        # ACCT_B: debit_volume=75000, credit_volume=100000
        assert acct_b["debit_credit_ratio"] == 0.75

    def test_max_single_txn_ratio(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_b = next(a for a in result["accounts"] if a["account_id"] == "ACCT_B")
        assert "max_single_txn_ratio" in acct_b
        # ACCT_B total=175000, max single=100000 → ratio ≈ 0.5714
        assert 0.5 < acct_b["max_single_txn_ratio"] < 0.6

    def test_single_txn_account_features(self, adapter):
        result = adapter.parse(SAMPLE_CSV)
        acct_c = next(a for a in result["accounts"] if a["account_id"] == "ACCT_C")
        # Only 1 credit txn, no debits → debit_credit_ratio = 0
        assert acct_c["debit_credit_ratio"] == 0.0
        # Only 1 balance → volatility = 0
        assert acct_c["balance_volatility"] == 0.0


class TestMuleCSVAdapterRealData:
    """Tests against the actual Sample Mule account data CSV."""

    @pytest.fixture
    def real_csv_content(self):
        csv_path = r"C:\Users\HP\Downloads\Sample Mule account data.csv"
        if not os.path.exists(csv_path):
            pytest.skip("Real CSV file not available")
        with open(csv_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_real_csv_parses_transactions(self, adapter, real_csv_content):
        result = adapter.parse(real_csv_content)
        # 2000 raw rows, but flow inference merges matched D+C pairs
        # into internal links, reducing total count
        assert len(result["transactions"]) >= 1900
        assert len(result["transactions"]) <= 2000

    def test_real_csv_derives_19_accounts(self, adapter, real_csv_content):
        result = adapter.parse(real_csv_content)
        assert len(result["accounts"]) == 19

    def test_real_csv_has_internal_links(self, adapter, real_csv_content):
        result = adapter.parse(real_csv_content)
        acc_ids = {a["account_id"] for a in result["accounts"]}
        internal = [
            t for t in result["transactions"]
            if t["from_account"] in acc_ids and t["to_account"] in acc_ids
        ]
        # Flow inference should create internal links between accounts
        assert len(internal) > 0

    def test_real_csv_detects_anomaly_flags(self, adapter, real_csv_content):
        result = adapter.parse(real_csv_content)
        assert len(result["anomaly_flags"]) > 0
        flag_types = {f["flag"] for f in result["anomaly_flags"]}
        assert "NEGATIVE_BALANCE" in flag_types
        assert "RAPID_SMALL_DEBITS" in flag_types
        assert "LAYERING_PATTERN" in flag_types


# ── Integration Tests: CSV Upload Endpoints ──────────────────────────────────


class TestCSVUploadEndpoints:
    """Integration tests for /api/v1/csv-upload/* endpoints.

    Note: These require a compatible starlette/httpx version.
    The same TestClient incompatibility affects all integration tests
    in this project (test_integration.py has the same issue).
    """

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from api.app import app
        try:
            return TestClient(app)
        except TypeError:
            pytest.skip("TestClient incompatible with installed starlette/httpx versions")

    @staticmethod
    def _data(response):
        body = response.json()
        assert body["success"] is True, f"Expected success=True, got: {body}"
        return body["data"]

    @staticmethod
    def _error(response):
        body = response.json()
        assert body["success"] is False
        return body["error"]

    def test_preview_before_upload_returns_not_loaded(self, client):
        r = client.get("/api/v1/csv-upload/preview")
        data = self._data(r)
        assert data["loaded"] is False

    def test_upload_valid_csv(self, client):
        r = client.post(
            "/api/v1/csv-upload/upload",
            files={"file": ("test.csv", SAMPLE_CSV.encode(), "text/csv")},
        )
        assert r.status_code == 200
        data = self._data(r)
        assert data["transactions"] == 10
        assert data["accounts"] == 3
        assert "channels" in data
        assert "UPI" in data["channels"]
        assert "preview_rows" in data
        assert len(data["preview_rows"]) <= 50
        assert "anomaly_flags" in data
        assert "account_summaries" in data

    def test_upload_rejects_non_csv(self, client):
        r = client.post(
            "/api/v1/csv-upload/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert r.status_code == 400
        error = self._error(r)
        assert error["code"] == "INVALID_FILE"

    def test_upload_rejects_empty_csv(self, client):
        empty = "TRAN_DATE|TRAN_ID|TRAN_TYPE|TRAN_SUB_TYPE|PART_TRAN_TYPE|ACID|TRAN_AMT|balance|channel|CIF_ID|ACCT_OPN_DATE|LIEN_AMT|customer_age\n"
        r = client.post(
            "/api/v1/csv-upload/upload",
            files={"file": ("empty.csv", empty.encode(), "text/csv")},
        )
        assert r.status_code == 400
        error = self._error(r)
        assert error["code"] == "EMPTY_DATA"

    def test_preview_after_upload_returns_loaded(self, client):
        # Upload first
        client.post(
            "/api/v1/csv-upload/upload",
            files={"file": ("test.csv", SAMPLE_CSV.encode(), "text/csv")},
        )
        r = client.get("/api/v1/csv-upload/preview")
        assert r.status_code == 200
        data = self._data(r)
        assert data["loaded"] is True
        assert data["transactions"] == 10
        assert data["accounts"] == 3
        assert "severity_counts" in data
        assert "channels" in data
