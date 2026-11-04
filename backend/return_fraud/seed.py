"""Seven demo scenarios, each built to land in a different decision tier.

Amounts are in rupees. Receipt files are tiny hand-made PDFs: enough for the metadata and hash checks,
not real invoices. The ring is five customers who share a device, an address and a card.
"""

from __future__ import annotations

import io
from typing import Dict, List

from pypdf import PdfWriter
from return_fraud.detectors import read_pdf_meta

SCENARIOS = (
    "legit",
    "receipt_manipulation",
    "exif_mismatch",
    "ring",
    "wardrobing",
    "friendly_fraud",
    "inr_carrier_fault",
)
DELIVERED = "2027-02-10T12:00:00+05:30"
GEO_BLR = [12.9716, 77.5946]
GEO_DEL = [28.6139, 77.2090]


RING_PHOTO_HASH = "c3a5b1e4d29f6078"  # the one photo every ring member sends in


def _pdf(tag: str, producer: str = "Zoho Invoice", modified: str = "D:20270210100000") -> bytes:
    """A valid one-page PDF whose metadata carries the producer and dates the receipt check reads."""
    writer = PdfWriter()
    writer.add_blank_page(width=210, height=297)
    writer.add_metadata(
        {"/Producer": producer, "/CreationDate": "D:20270210100000", "/ModDate": modified, "/Subject": tag}
    )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _exif(**kw) -> Dict:
    return {"taken_at": "2027-02-12T10:00:00+05:30", "model": "Pixel 7", "software": "", "geo": GEO_BLR, **kw}


def _claim(claim_id: str, scenario: str, **kw) -> Dict:
    base = {
        "claim_id": claim_id,
        "scenario": scenario,
        "currency": "INR",
        "delivered_at": DELIVERED,
        "returned_at": "2027-02-14T12:00:00+05:30",
        "delivery_geo": GEO_BLR,
        "expected_device": "Pixel 7",
        "history": {"orders_90d": 12, "returns_90d": 1, "account_age_days": 700},
        "carrier_fault": False,
        "carrier_events": [],
        "chargebacks": [],
    }
    claim = {**base, **kw}
    if claim.get("receipt_pdf"):
        claim["receipt_meta"] = read_pdf_meta(claim["receipt_pdf"])  # parsed once here, like a filed claim
    return claim


def _legit() -> List[Dict]:
    return [
        _claim(
            "RC-1001", "legit", customer_id="C-ANITA", customer_name="Anita Rao", item="Wireless headphones",
            category="electronics", amount=4200, reason_text="Left earcup cracked on arrival",
            device_id="D-ANITA", address="14 Lake View, Bengaluru", payment_fp="P-ANITA",
            exif=_exif(), photo_labels=["cracked", "earcup"], receipt_pdf=_pdf("RC-1001"), receipt_amount=4200,
        )
    ]  # fmt: skip


def _receipt_manipulation() -> List[Dict]:
    return [
        _claim(
            "RC-1002", "receipt_manipulation", customer_id="C-VIKRAM", customer_name="Vikram Shah",
            item="Laptop sleeve and dock", category="electronics", amount=18500,
            reason_text="Dock stopped working", device_id="D-VIKRAM", address="7 Ring Road, Surat",
            payment_fp="P-VIKRAM", exif=_exif(geo=[21.17, 72.83], model="Pixel 7"),
            delivery_geo=[21.17, 72.83], photo_labels=["dead", "dock"],
            receipt_pdf=_pdf("RC-1002", producer="Adobe Photoshop 25", modified="D:20270213100000"),
            receipt_amount=9500,
        )
    ]  # fmt: skip


def _exif_mismatch() -> List[Dict]:
    return [
        _claim(
            "RC-1003", "exif_mismatch", customer_id="C-MEERA", customer_name="Meera Nair",
            item="27-inch monitor", category="electronics", amount=32000,
            reason_text="Screen cracked in transit", device_id="D-MEERA", address="3 Marine Drive, Kochi",
            payment_fp="P-MEERA",
            exif=_exif(taken_at="2027-02-01T10:00:00+05:30", software="Adobe Photoshop 25"),
            photo_labels=["intact", "screen", "no damage"], receipt_pdf=_pdf("RC-1003"), receipt_amount=32000,
        )
    ]  # fmt: skip


def _ring() -> List[Dict]:
    shared = {"device_id": "D-RING", "address": "21 Canal Street, Kolkata", "payment_fp": "P-RING"}
    stolen_receipt = _pdf("RING-RECEIPT", producer="Canva", modified="D:20270212100000")
    members = []
    for i, name in enumerate(("Rohit Das", "Sneha Paul", "Imran Khan", "Tara Bose", "Dev Ghosh"), start=4):
        members.append(
            _claim(
                f"RC-100{i}", "ring", customer_id=f"C-RING{i}", customer_name=name, item="Smartphone",
                category="electronics", amount=54000, reason_text="Phone arrived damaged, screen cracked",
                exif=_exif(taken_at="2027-02-02T10:00:00+05:30", software="Adobe Photoshop 25", model="iPhone 15"),
                photo_labels=["intact", "no damage"], receipt_pdf=stolen_receipt, receipt_amount=54000,
                photo_phash=RING_PHOTO_HASH, returned_at="2027-02-10T20:00:00+05:30",
                history={"orders_90d": 3, "returns_90d": 3, "account_age_days": 12},
                headline=(i == 8), **shared,
            )
        )  # fmt: skip
    return members


def _wardrobing() -> List[Dict]:
    return [
        _claim(
            "RC-1009", "wardrobing", customer_id="C-NISHA", customer_name="Nisha Verma",
            item="Silk lehenga", category="apparel", amount=12000, reason_text="Did not fit",
            event_date="2027-02-13", device_id="D-NISHA", address="88 Civil Lines, Jaipur",
            payment_fp="P-NISHA", history={"orders_90d": 6, "returns_90d": 4, "account_age_days": 400},
            receipt_pdf=_pdf("RC-1009"), receipt_amount=12000,
        )
    ]  # fmt: skip


def _friendly_fraud() -> List[Dict]:
    return [
        _claim(
            "RC-1010", "friendly_fraud", customer_id="C-KARAN", customer_name="Karan Mehta",
            item="Running shoes", category="apparel", amount=6500, reason_text="Item never received",
            returned_at="2027-02-11T09:00:00+05:30", device_id="D-KARAN", address="5 Hill Road, Mumbai",
            payment_fp="P-KARAN", history={"orders_90d": 10, "returns_90d": 7, "account_age_days": 900},
            carrier_events=[{"type": "delivered", "at": DELIVERED, "signed_by": "K. Mehta"}],
            receipt_pdf=_pdf("RC-1010"), receipt_amount=6500,
        )
    ]  # fmt: skip


def _inr_carrier_fault() -> List[Dict]:
    return [
        _claim(
            "RC-1011", "inr_carrier_fault", customer_id="C-LAKSHMI", customer_name="Lakshmi Iyer",
            item="Flagship smartphone", category="electronics", amount=185000,
            reason_text="Back glass cracked, box was crushed", device_id="D-LAKSHMI",
            address="9 Temple Road, Chennai", payment_fp="P-LAKSHMI", carrier_fault=True,
            carrier_events=[{"type": "damaged_in_transit", "at": "2027-02-09T18:00:00+05:30"}],
            exif=_exif(model="Galaxy S24", geo=GEO_DEL), photo_labels=["crack", "back glass"],
            history={"orders_90d": 9, "returns_90d": 3, "account_age_days": 900},
            receipt_pdf=_pdf("RC-1011"), receipt_amount=185000,
        )
    ]  # fmt: skip


def seed_claims() -> List[Dict]:
    return [
        *_legit(),
        *_receipt_manipulation(),
        *_exif_mismatch(),
        *_ring(),
        *_wardrobing(),
        *_friendly_fraud(),
        *_inr_carrier_fault(),
    ]
