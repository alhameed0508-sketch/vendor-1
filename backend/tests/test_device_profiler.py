"""Tests for device profiling service."""

import time
import pytest
from models.device.device_profiler import (
    DeviceProfiler,
    DeviceTrustResult,
)


@pytest.fixture
def profiler():
    return DeviceProfiler()


class TestDeviceTrustResult:
    def test_frozen(self):
        result = DeviceTrustResult(
            account_id="A",
            device_trust_score=0.5,
            device_count=1,
            recent_switches_24h=0,
            shared_device_accounts=(),
            reason_codes=(),
        )
        with pytest.raises(AttributeError):
            result.device_trust_score = 0.9


class TestRecordDeviceEvent:
    def test_basic_recording(self, profiler):
        profiler.record_device_event("ACC_001", "DEV_A")
        result = profiler.compute_trust("ACC_001")
        assert result.device_count == 1
        assert result.device_trust_score == 0.0

    def test_multiple_devices(self, profiler):
        profiler.record_device_event("ACC_001", "DEV_A")
        profiler.record_device_event("ACC_001", "DEV_B")
        result = profiler.compute_trust("ACC_001")
        assert result.device_count == 2
        assert "DP01" in result.reason_codes[0]


class TestDP01MultipleDevices:
    def test_four_devices_high_risk(self, profiler):
        for i in range(4):
            profiler.record_device_event("ACC_001", f"DEV_{i}")
        result = profiler.compute_trust("ACC_001")
        assert result.device_trust_score > 0.5


class TestDP02RapidSwitching:
    def test_rapid_switches(self, profiler):
        now = time.time()
        profiler.record_device_event("ACC_001", "DEV_A", now - 3600)
        profiler.record_device_event("ACC_001", "DEV_B", now - 2400)
        profiler.record_device_event("ACC_001", "DEV_C", now - 1200)
        profiler.record_device_event("ACC_001", "DEV_A", now)
        result = profiler.compute_trust("ACC_001")
        assert result.recent_switches_24h >= 3
        assert any("DP02" in rc for rc in result.reason_codes)


class TestDP03SharedFlagged:
    def test_shared_with_flagged(self, profiler):
        profiler.record_device_event("MULE_001", "SHARED_DEV", is_flagged=True)
        profiler.record_device_event("ACC_001", "SHARED_DEV")
        result = profiler.compute_trust("ACC_001")
        assert "MULE_001" in result.shared_device_accounts
        assert any("DP03" in rc for rc in result.reason_codes)


class TestDP04Emulator:
    def test_emulator_detection(self, profiler):
        profiler.record_device_event("ACC_001", "sdk_gphone_x86_emulator")
        result = profiler.compute_trust("ACC_001")
        assert any("DP04" in rc for rc in result.reason_codes)

    def test_normal_device(self, profiler):
        profiler.record_device_event("ACC_001", "samsung_galaxy_s21")
        result = profiler.compute_trust("ACC_001")
        assert not any("DP04" in rc for rc in result.reason_codes)

    def test_explicit_bot_indicator(self, profiler):
        profiler.record_device_event(
            "ACC_001",
            "hashed-device-id",
            risk_indicators=("bot",),
        )
        result = profiler.compute_trust("ACC_001")
        assert any("DP05" in rc for rc in result.reason_codes)


class TestCompositeScore:
    def test_clean_account(self, profiler):
        profiler.record_device_event("ACC_001", "DEV_A")
        result = profiler.compute_trust("ACC_001")
        assert result.device_trust_score == 0.0

    def test_no_events(self, profiler):
        result = profiler.compute_trust("UNKNOWN")
        assert result.device_trust_score == 0.0
        assert result.device_count == 0

    def test_score_bounded(self, profiler):
        now = time.time()
        for i in range(10):
            profiler.record_device_event(
                "BAD", f"emulator_dev_{i}", now - i * 100, is_flagged=True
            )
        profiler.record_device_event("SUSPECT", "emulator_dev_0", now)
        result = profiler.compute_trust("SUSPECT")
        assert 0.0 <= result.device_trust_score <= 1.0


class TestDeviceStats:
    def test_stats(self, profiler):
        profiler.record_device_event("A1", "D1")
        profiler.record_device_event("A2", "D2", is_flagged=True)
        stats = profiler.get_device_stats()
        assert stats["total_accounts_tracked"] == 2
        assert stats["total_devices_seen"] == 2
        assert stats["flagged_accounts"] == 1
