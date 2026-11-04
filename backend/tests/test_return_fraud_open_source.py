"""Checks built on open-source libraries: ImageHash (photo reuse), pypdf (receipt file) and RapidFuzz (claim text)."""

import io

import pytest
from PIL import Image, ImageDraw
from return_fraud.assess import assess_claim
from return_fraud.detectors import exif_signal, graph_signal, photo_hash, read_pdf_meta, receipt_signal
from return_fraud.seed import _pdf, seed_claims

BASE = {
    "claim_id": "RC-1", "customer_id": "C1", "amount": 8000, "category": "electronics",
    "delivered_at": "2027-02-10T12:00:00+05:30", "reason_text": "Screen cracked on arrival",
    "device_id": "D1", "address": "A1", "payment_fp": "P1",
}  # fmt: skip


def _png(size=(200, 200), shade=40) -> bytes:
    img = Image.new("RGB", size, (shade, shade, shade))
    ImageDraw.Draw(img).rectangle([30, 40, 150, 120], fill=(250, 250, 250))
    ImageDraw.Draw(img).ellipse([90, 90, 180, 180], fill=(10, 10, 200))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_a_resized_copy_of_a_photo_has_the_same_hash():
    original = Image.open(io.BytesIO(_png((400, 400))))
    buf = io.BytesIO()
    original.resize((100, 100)).save(buf, "JPEG")
    big, small = photo_hash(_png((400, 400))), photo_hash(buf.getvalue())
    assert big and small
    assert bin(int(big, 16) ^ int(small, 16)).count("1") <= 6


def test_unreadable_bytes_give_no_hash():
    assert photo_hash(b"not an image") is None


def test_same_photo_from_another_customer_is_flagged():
    h = photo_hash(_png())
    mine = {**BASE, "exif": {"model": "Pixel 7"}, "photo_phash": h}
    theirs = {**BASE, "claim_id": "RC-0", "customer_id": "C2", "photo_phash": h}
    s = exif_signal(mine, [theirs])
    assert s.score >= 55
    assert "RC-0" in s.reasons[0]
    assert s.detail_dict["reused_from"] == "RC-0"


def test_reuse_is_flagged_even_when_the_metadata_was_stripped():
    h = photo_hash(_png())
    s = exif_signal(
        {**BASE, "exif": {}, "photo_phash": h}, [{**BASE, "claim_id": "RC-0", "customer_id": "C2", "photo_phash": h}]
    )
    assert s.score >= 55


def test_the_same_customer_reusing_their_own_photo_is_not_flagged():
    h = photo_hash(_png())
    mine = {**BASE, "exif": {"model": "Pixel 7"}, "photo_phash": h}
    assert exif_signal(mine, [{**BASE, "claim_id": "RC-0", "photo_phash": h}]).score < 20


def test_different_photos_do_not_match():
    other = Image.new("RGB", (200, 200), (255, 0, 0))
    buf = io.BytesIO()
    ImageDraw.Draw(other).line([0, 0, 200, 200], fill=(0, 0, 0), width=30)
    other.save(buf, "PNG")
    mine = {**BASE, "exif": {"model": "Pixel 7"}, "photo_phash": photo_hash(_png())}
    theirs = {**BASE, "claim_id": "RC-0", "customer_id": "C2", "photo_phash": photo_hash(buf.getvalue())}
    assert exif_signal(mine, [theirs]).score < 20


def test_pdf_metadata_is_read_by_pypdf():
    meta = read_pdf_meta(_pdf("T", producer="Canva", modified="D:20270212100000"))
    assert meta["producer"] == "Canva"
    assert meta["modified"].day == 12


def test_a_file_saved_again_after_it_was_generated_is_flagged():
    edited = _pdf("T") + b"\n1 0 obj<</Producer(Zoho Invoice)>>endobj\n%%EOF"
    assert read_pdf_meta(edited)["updates"] == 1
    s = receipt_signal({**BASE, "receipt_pdf": edited}, {})
    assert s.score >= 30
    assert any("more time" in r for r in s.reasons)


def test_a_damaged_pdf_falls_back_to_its_bytes():
    meta = read_pdf_meta(b"%PDF-1.4 garbage /Producer(Gimp) more garbage")
    assert meta["producer"] == "Gimp"


def test_a_ring_with_near_identical_words_says_so():
    ring = [
        {**BASE, "claim_id": f"RC-{i}", "customer_id": f"C{i}", "reason_text": "Phone arrived damaged, screen cracked"}
        for i in range(1, 5)
    ]
    s = graph_signal(ring[0], ring[1:])
    assert s.detail_dict["similar_text_percent"] == 100
    assert any("almost the same words" in r for r in s.reasons)


def test_a_ring_with_different_words_gets_no_text_note():
    texts = ["Phone arrived damaged", "Wrong colour sent", "Battery drains fast", "Case is missing"]
    ring = [{**BASE, "claim_id": f"RC-{i}", "customer_id": f"C{i}", "reason_text": t} for i, t in enumerate(texts, 1)]
    assert graph_signal(ring[0], ring[1:]).detail_dict["similar_text_percent"] is None


@pytest.fixture(scope="module")
def ring_result():
    claims = seed_claims()
    head = next(c for c in claims if c.get("headline"))
    return assess_claim(head, claims)


def test_seeded_ring_shows_photo_reuse_and_text_match(ring_result):
    by = {s["name"]: s for s in ring_result["signals"]}
    assert by["exif"]["detail"]["reused_from"]
    assert by["graph"]["detail"]["similar_text_percent"] == 100


def test_every_signal_names_its_source(ring_result):
    assert all(s["source"] for s in ring_result["signals"])


def test_a_fired_signal_lists_the_others_that_agree(ring_result):
    fired = [s for s in ring_result["signals"] if s["corroborated_by"]]
    assert len(fired) >= 3
    for s in fired:
        assert s["name"] not in s["corroborated_by"]


def test_a_quiet_signal_has_no_corroboration():
    claims = seed_claims()
    legit = next(c for c in claims if c["scenario"] == "legit")
    assert all(s["corroborated_by"] == [] for s in assess_claim(legit, claims)["signals"])
