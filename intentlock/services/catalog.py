"""Catalogue adapters. The demo catalogue is the only source the first merchant can take payment for.

Product text (title, description, seller metadata) is untrusted data. It is displayed and may be shown to a
model as quoted data, but it never becomes an instruction and never changes a mandate or a policy result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from intentlock.db.models import Product
from intentlock.domain import OfferFacts

DEMO_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_catalog.json"


class CatalogProvider(Protocol):
    source: str

    def all(self) -> list[OfferFacts]: ...


class DemoCatalogProvider:
    source = "demo_catalogue"

    def __init__(self, path: Path = DEMO_CATALOG_PATH) -> None:
        self._path = path

    def all(self) -> list[OfferFacts]:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        sellers, currency = raw["sellers"], raw["currency"]
        return [
            OfferFacts(**p, currency=currency, seller_name=sellers[p["seller_id"]], source=self.source, source_reference=f"demo_catalog.json#{p['product_id']}")
            for p in raw["products"]
        ]


def sync_products(s: Session, provider: CatalogProvider) -> int:
    """Upsert the provider's offers into `products`, so quotes and receipts reference stored rows."""
    existing = {p.provider_product_id: p for p in s.scalars(select(Product).where(Product.source == provider.source))}
    offers = provider.all()
    for o in offers:
        row = existing.get(o.product_id) or Product(provider_product_id=o.product_id, source=o.source)
        row.title, row.description, row.category, row.condition = o.title, o.description, o.category.lower(), o.condition
        row.attributes, row.seller_id, row.seller_name = dict(o.attributes), o.seller_id, o.seller_name
        row.merchant_checkout_eligible, row.availability_status = o.merchant_checkout_eligible, o.availability_status
        row.currency, row.unit_amount_minor = o.currency, o.unit_amount_minor
        row.shipping_amount_minor, row.tax_amount_minor = o.shipping_amount_minor, o.tax_amount_minor
        row.source_reference, row.synthetic = o.source_reference, True
        s.add(row)
    s.commit()
    return len(offers)


def offer_of(p: Product) -> OfferFacts:
    return OfferFacts(
        product_id=p.provider_product_id, title=p.title, description=p.description, category=p.category, condition=p.condition,
        attributes=p.attributes or {}, seller_id=p.seller_id, seller_name=p.seller_name,
        merchant_checkout_eligible=p.merchant_checkout_eligible, availability_status=p.availability_status,
        unit_amount_minor=p.unit_amount_minor, currency=p.currency, shipping_amount_minor=p.shipping_amount_minor,
        tax_amount_minor=p.tax_amount_minor, source=p.source, source_reference=p.source_reference,
    )  # fmt: skip


def get_product(s: Session, product_id: str) -> Product | None:
    return s.scalars(select(Product).where(Product.provider_product_id == product_id)).first()


def search(s: Session, *, category: str | None = None, text: str | None = None, limit: int = 50) -> list[Product]:
    q = select(Product).order_by(Product.unit_amount_minor)
    if category:
        q = q.where(Product.category == category.strip().lower())
    rows = list(s.scalars(q))
    words = [w for w in (text or "").lower().split() if len(w) > 2]
    if words:
        rows = [r for r in rows if any(w in f"{r.title} {r.description} {r.category}".lower() for w in words)] or rows
    return rows[:limit]


def product_view(p: Product) -> dict:
    total = None if p.shipping_amount_minor is None or p.tax_amount_minor is None else p.unit_amount_minor + p.shipping_amount_minor + p.tax_amount_minor
    return {
        "product_id": p.provider_product_id, "title": p.title, "description": p.description, "category": p.category,
        "condition": p.condition, "attributes": p.attributes, "seller_id": p.seller_id, "seller_name": p.seller_name,
        "merchant_checkout_eligible": p.merchant_checkout_eligible, "availability_status": p.availability_status,
        "currency": p.currency, "unit_amount_minor": p.unit_amount_minor, "shipping_amount_minor": p.shipping_amount_minor,
        "tax_amount_minor": p.tax_amount_minor, "total_for_one_minor": total, "source": p.source,
        "source_reference": p.source_reference, "synthetic": p.synthetic,
    }  # fmt: skip
