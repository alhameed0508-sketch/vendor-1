"""Return-claim API: scoring, review, bank package and signed webhooks."""

import base64
import hashlib
import hmac
import json
from datetime import datetime

import pytest
import pytest_asyncio
from api.deps import get_audit_service, get_return_claim_service
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from repositories.return_claim_repository import ReturnClaimRepository
from services.return_claim_service import ReturnClaimService

from infra.security.auth import create_access_token

SECRET = "webhook-secret-for-tests"


def _headers(role):
    return {"Authorization": f"Bearer {create_access_token(role.lower(), role)}"}


GUEST, INVESTIGATOR, SUPERVISOR = _headers("GUEST"), _headers("INVESTIGATOR"), _headers("SUPERVISOR")
NEW_CLAIM = {
    "customer_id": "C-NEW",
    "customer_name": "Test Buyer",
    "item": "Kettle",
    "category": "home",
    "amount": 2500,
    "reason_text": "Lid is broken",
    "delivered_at": "2027-02-10T12:00:00+05:30",
    "returned_at": "2027-02-12T12:00:00+05:30",
    "device_id": "D-NEW",
    "photo_labels": ["broken", "lid"],
    "history": {"orders_90d": 5, "returns_90d": 0, "account_age_days": 500},
}


@pytest.fixture
def service():
    svc = ReturnClaimService(
        repo=ReturnClaimRepository(),
        audit=get_audit_service(),
        provider=None,
        now_fn=lambda: datetime.fromisoformat("2027-03-01T10:00:00+05:30"),
        webhook_secret=SECRET,
    )
    svc.seed_demo()
    return svc


@pytest_asyncio.fixture
async def client(monkeypatch, service):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_for_testing_only_32chars")
    get_settings.cache_clear()
    from api.app import app

    app.dependency_overrides[get_return_claim_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_return_claim_service, None)
    get_settings.cache_clear()


def _signed(payload, secret=SECRET):
    body = json.dumps(payload).encode()
    return {
        "content": body,
        "headers": {"X-MuleCatch-Signature": hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()},
    }


@pytest.mark.asyncio
async def test_list_orders_claims_by_score_with_counts(client):
    r = await client.get("/api/v1/returns", headers=GUEST)
    data = r.json()["data"]
    assert r.status_code == 200
    scores = [c["score"] for c in data["claims"]]
    assert scores == sorted(scores, reverse=True)
    assert data["summary"]["by_tier"]["BLOCK"] >= 1
    assert data["summary"]["total"] == len(data["claims"])


@pytest.mark.asyncio
async def test_overview_covers_scenarios_rings_and_signal_reach(client):
    data = (await client.get("/api/v1/returns/overview", headers=GUEST)).json()["data"]
    assert {s["scenario"] for s in data["scenarios"]} >= {"legit", "ring", "wardrobing"}
    assert data["rings"] and data["rings"][0]["customers"] == 5
    assert set(data["signal_coverage"]) == {"exif", "vlm", "receipt", "device", "behavioral", "graph"}
    assert data["signal_coverage"]["receipt"]["fired"] >= 1


@pytest.mark.asyncio
async def test_claim_detail_shows_six_signals_and_no_raw_files(client):
    data = (await client.get("/api/v1/returns/RC-1008", headers=GUEST)).json()["data"]
    assert len(data["signals"]) == 6
    assert data["fusion"]["tier"] == "BLOCK"
    assert "receipt_pdf" not in json.dumps(data)


@pytest.mark.asyncio
async def test_unknown_claim_is_404(client):
    assert (await client.get("/api/v1/returns/RC-0", headers=GUEST)).status_code == 404


@pytest.mark.asyncio
async def test_guest_cannot_file_or_review(client):
    assert (await client.post("/api/v1/returns", json=NEW_CLAIM, headers=GUEST)).status_code == 403
    assert (
        await client.post("/api/v1/returns/RC-1008/review", json={"outcome": "reject"}, headers=GUEST)
    ).status_code == 403


@pytest.mark.asyncio
async def test_investigator_files_a_claim_and_it_is_scored(client):
    r = await client.post("/api/v1/returns", json=NEW_CLAIM, headers=INVESTIGATOR)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["fusion"]["tier"] == "APPROVE"


@pytest.mark.asyncio
async def test_photo_and_receipt_uploads_feed_the_signals(client):
    import io

    from PIL import Image

    img = Image.new("RGB", (4, 4))
    exif = img.getexif()
    exif[0x0131] = "Adobe Photoshop"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    body = {**NEW_CLAIM, "photo_b64": base64.b64encode(buf.getvalue()).decode()}
    data = (await client.post("/api/v1/returns", json=body, headers=INVESTIGATOR)).json()["data"]
    exif_signal = next(s for s in data["signals"] if s["name"] == "exif")
    assert exif_signal["score"] >= 30


@pytest.mark.asyncio
async def test_bad_base64_is_rejected(client):
    r = await client.post("/api/v1/returns", json={**NEW_CLAIM, "photo_b64": "!!!"}, headers=INVESTIGATOR)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_return_before_delivery_is_rejected(client):
    r = await client.post(
        "/api/v1/returns", json={**NEW_CLAIM, "returned_at": "2027-02-01T00:00:00+05:30"}, headers=INVESTIGATOR
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_only_supervisor_reviews_and_only_once(client):
    assert (
        await client.post("/api/v1/returns/RC-1008/review", json={"outcome": "reject"}, headers=INVESTIGATOR)
    ).status_code == 403
    ok = await client.post(
        "/api/v1/returns/RC-1008/review", json={"outcome": "escalate", "notes": "ring"}, headers=SUPERVISOR
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["review"]["recommended_tier"] == "BLOCK"
    again = await client.post("/api/v1/returns/RC-1008/review", json={"outcome": "reject"}, headers=SUPERVISOR)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_package_json_verifies_and_pdf_downloads(client):
    pkg = (await client.get("/api/v1/returns/RC-1008/package", headers=GUEST)).json()["data"]
    assert pkg["verification"]["intact"] is True
    pdf = await client.get("/api/v1/returns/RC-1008/package.pdf", headers=GUEST)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "RC-1008_bank_package.pdf" in pdf.headers["content-disposition"]


@pytest.mark.asyncio
async def test_carrier_webhook_with_valid_signature_eases_the_score(client):
    before = (await client.get("/api/v1/returns/RC-1003", headers=GUEST)).json()["data"]["fusion"]["raw_score"]
    event = {
        "claim_id": "RC-1003",
        "event": "damaged_in_transit",
        "occurred_at": "2027-02-09T18:00:00+05:30",
        "carrier": "Bluedart",
    }
    r = await client.post("/api/v1/returns/webhooks/carrier", **_signed(event))
    assert r.status_code == 200 and r.json()["data"]["duplicate"] is False
    after = (await client.get("/api/v1/returns/RC-1003", headers=GUEST)).json()["data"]["fusion"]["raw_score"]
    assert after < before
    again = await client.post("/api/v1/returns/webhooks/carrier", **_signed(event))
    assert again.json()["data"]["duplicate"] is True


@pytest.mark.asyncio
async def test_webhook_with_bad_signature_is_refused(client):
    event = {"claim_id": "RC-1003", "event": "delivered", "occurred_at": "2027-02-09T18:00:00+05:30"}
    r = await client.post("/api/v1/returns/webhooks/carrier", **_signed(event, secret="wrong"))
    assert r.status_code == 401
    r = await client.post("/api/v1/returns/webhooks/carrier", content=json.dumps(event))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_chargeback_webhook_is_recorded_once(client):
    event = {
        "claim_id": "RC-1008",
        "chargeback_id": "CB-9",
        "status": "opened",
        "reason_code": "4837",
        "amount": 54000,
        "occurred_at": "2027-02-20T10:00:00+05:30",
    }
    first = await client.post("/api/v1/returns/webhooks/chargeback", **_signed(event))
    second = await client.post("/api/v1/returns/webhooks/chargeback", **_signed(event))
    assert first.json()["data"]["duplicate"] is False and second.json()["data"]["duplicate"] is True
    claim = (await client.get("/api/v1/returns/RC-1008", headers=GUEST)).json()["data"]["claim"]
    assert len(claim["chargebacks"]) == 1


@pytest.mark.asyncio
async def test_webhook_for_unknown_claim_is_404(client):
    event = {"claim_id": "RC-0", "event": "delivered", "occurred_at": "2027-02-09T18:00:00+05:30"}
    assert (await client.post("/api/v1/returns/webhooks/carrier", **_signed(event))).status_code == 404


@pytest.mark.asyncio
async def test_unsigned_webhooks_fail_closed_in_production(monkeypatch, service):
    service._secret = ""
    with pytest.raises(Exception) as exc:
        service.check_signature(b"{}", None, strict=True)
    assert "secret" in str(exc.value).lower()
    service.check_signature(b"{}", None, strict=False)  # demo mode accepts unsigned


@pytest.mark.asyncio
async def test_claim_detail_carries_the_three_part_narrative_and_category(client):
    data = (await client.get("/api/v1/returns/RC-1008", headers=GUEST)).json()["data"]
    assert set(data["narrative"]) == {"what_happened", "what_we_found", "what_we_recommend"}
    assert data["dispute_category"]["code"] == "RING"


@pytest.mark.asyncio
async def test_provider_is_called_once_when_a_claim_is_filed_and_never_on_reads(client, service):
    provider = _CountingProvider()
    service._provider = provider
    filed = (await client.post("/api/v1/returns", json=NEW_CLAIM, headers=INVESTIGATOR)).json()["data"]
    assert provider.calls == 1
    for path in ("", "/overview", f"/{filed['claim']['claim_id']}", "/RC-1008/package"):
        assert (await client.get(f"/api/v1/returns{path}", headers=GUEST)).status_code == 200
    assert provider.calls == 1


class _CountingProvider:
    provider_name = "fake"
    calls = 0

    def generate(self, messages, **kwargs):
        self.calls += 1

        class R:
            content = '{"score": 20}'

        return R()


@pytest.mark.asyncio
async def test_receipt_is_parsed_once_when_filed_and_never_on_reads(client, monkeypatch):
    import return_fraud.detectors as detectors

    calls = []
    real = detectors.read_pdf_meta
    monkeypatch.setattr(detectors, "read_pdf_meta", lambda raw: calls.append(1) or real(raw))
    import services.return_claim_service as svc

    monkeypatch.setattr(svc, "read_pdf_meta", detectors.read_pdf_meta)
    pdf = b"%PDF-1.4\n1 0 obj<</Producer(Zoho Invoice)>>endobj\n%%EOF"
    body = {**NEW_CLAIM, "receipt_pdf_b64": base64.b64encode(pdf).decode()}
    created = (await client.post("/api/v1/returns", json=body, headers=INVESTIGATOR)).json()["data"]
    assert len(calls) == 1
    claim_id = created["claim"]["claim_id"]
    for _ in range(3):
        await client.get(f"/api/v1/returns/{claim_id}", headers=INVESTIGATOR)
        await client.get("/api/v1/returns", headers=INVESTIGATOR)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_a_photo_too_large_to_check_is_reported_not_skipped(client, monkeypatch):
    import io

    import return_fraud.detectors as detectors
    from PIL import Image

    monkeypatch.setattr(detectors, "MAX_PHOTO_PIXELS", 100)
    buf = io.BytesIO()
    Image.new("RGB", (20, 20)).save(buf, "PNG")
    body = {**NEW_CLAIM, "photo_b64": base64.b64encode(buf.getvalue()).decode()}
    data = (await client.post("/api/v1/returns", json=body, headers=INVESTIGATOR)).json()["data"]
    exif_signal = next(s for s in data["signals"] if s["name"] == "exif")
    assert exif_signal["score"] >= 30
    assert "too large" in exif_signal["reasons"][0]
    assert exif_signal["detail"].get("photo_phash") is None


def test_the_pixel_cap_stops_hashing_and_metadata_reading(monkeypatch):
    import io

    import return_fraud.detectors as detectors
    from PIL import Image

    monkeypatch.setattr(detectors, "MAX_PHOTO_PIXELS", 100)
    buf = io.BytesIO()
    img = Image.new("RGB", (20, 20))
    exif = img.getexif()
    exif[0x0131] = "Gimp"
    img.save(buf, "JPEG", exif=exif)
    assert detectors.photo_too_large(buf.getvalue())
    assert detectors.photo_hash(buf.getvalue()) is None
    assert detectors.read_exif(buf.getvalue()) == {"software": "Gimp"}  # a JPEG's header is cheap to read


def test_oversized_png_metadata_is_not_read(monkeypatch):
    import io

    import return_fraud.detectors as detectors
    from PIL import Image

    monkeypatch.setattr(detectors, "MAX_PHOTO_PIXELS", 100)
    buf = io.BytesIO()
    Image.new("RGB", (20, 20)).save(buf, "PNG")
    assert detectors.read_exif(buf.getvalue()) == {}


def test_busy_parsers_defer_the_receipt_without_a_penalty_and_try_again_later():
    import return_fraud.detectors as detectors

    raw = b"%PDF-1.4 /Producer(Gimp)"
    held = [detectors._PDF_SLOTS.acquire(blocking=False) for _ in range(detectors.PDF_PARSERS)]
    try:
        assert all(held)
        meta = detectors.read_pdf_meta(raw)
        assert meta["reader"] == "deferred" and meta["producer"] == "Gimp"
        busy = detectors.receipt_signal({"receipt_pdf": raw, "receipt_meta": meta, "claim_id": "x"}, {})
    finally:
        for _ in held:
            detectors._PDF_SLOTS.release()
    assert not any("basic scan" in r for r in busy.reasons)
    assert detectors.read_pdf_meta(raw)["reader"] == "bytes"  # a free slot, but pypdf cannot read this file


def test_pdf_parsing_is_capped_and_falls_back_to_bytes_when_all_parsers_are_busy():
    import return_fraud.detectors as detectors

    held = [detectors._PDF_SLOTS.acquire(blocking=False) for _ in range(detectors.PDF_PARSERS)]
    try:
        assert all(held)
        meta = detectors.read_pdf_meta(b"%PDF-1.4 /Producer(Gimp)")
        assert meta["producer"] == "Gimp"
    finally:
        for _ in held:
            detectors._PDF_SLOTS.release()
