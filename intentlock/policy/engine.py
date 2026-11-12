"""Deterministic purchase-policy engine.

Pure functions: no database, no network, no model calls. Given the confirmed mandate, the offer, the server
quote and (before capture) the payment provider's order, it returns a decision with one record per rule.

Decision rule (fixed, not configurable by any model):
  * a limit the buyer set is broken                -> BLOCK
  * what the buyer approved has changed            -> REAUTHORISE
  * data needed for a rule is missing or stale     -> REVIEW
  * several rules fire                             -> BLOCK, then REAUTHORISE, then REVIEW
  * every rule passes                              -> ALLOW
"""

from __future__ import annotations

from datetime import datetime

from intentlock.domain import (
    CheckStatus,
    Decision,
    Evaluation,
    ExpectedOrder,
    MandateSpec,
    MandateState,
    OfferFacts,
    OrderFacts,
    PolicyCheck,
    QuoteFacts,
)
from intentlock.money import display

POLICY_VERSION = "intentlock-policy-2026.11.1"

# The rule register: every rule the engine can apply, in evaluation order. SPEC_* stands for one rule per must-have.
# Fields: rule_id, stage, decision when it fails, short title, what it checks.
RULES = (
    ("MANDATE_ACTIVE", "PRE_ORDER", "BLOCK", "Mandate is active", "The mandate is confirmed, is the current version, and has not been revoked or expired."),
    ("PRODUCT_CATEGORY", "PRE_ORDER", "BLOCK", "Right kind of product", "The product is the kind of item the mandate is for."),
    ("PRODUCT_CONDITION", "PRE_ORDER", "BLOCK", "Right condition", "The product is new, used or refurbished, as the mandate requires."),
    ("SPEC_*", "PRE_ORDER", "BLOCK", "Must-haves are met", "Each must-have is met, such as memory of at least 16 GB. If the catalogue does not state the value, the result is REVIEW."),
    ("SUBSTITUTION", "PRE_ORDER", "REAUTHORISE", "No unapproved substitute", "If the buyer named a model, a different one needs the buyer's approval unless substitutes are allowed."),
    ("QUANTITY", "PRE_ORDER", "REAUTHORISE", "Right quantity", "The quote is for the quantity in the mandate."),
    ("APPROVED_SELLER", "PRE_ORDER", "BLOCK", "Approved seller", "The seller is on the buyer's approved list, unless any seller is allowed."),
    ("MERCHANT_CHECKOUT_ELIGIBLE", "PRE_ORDER", "BLOCK", "Payable through this store", "This merchant is authorised to take payment for the product."),
    ("AVAILABILITY", "PRE_ORDER", "REVIEW", "In stock", "The product is in stock."),
    ("CURRENCY", "PRE_ORDER", "REAUTHORISE", "Mandate currency", "The quote is in the mandate's currency."),
    ("MAXIMUM_TOTAL", "PRE_ORDER", "BLOCK", "Within budget", "The total, with shipping and tax when the budget covers them, is within the budget. Unknown shipping or tax gives REVIEW; it is never taken as zero."),
    ("QUOTE_FRESH", "PRE_ORDER", "REVIEW", "Quote still valid", "The server's quote has not expired."),
    ("ORDER_ID", "PRE_CAPTURE", "BLOCK", "Same PayPal order", "PayPal returned the order this checkout created."),
    ("ORDER_APPROVED_BY_BUYER", "PRE_CAPTURE", "REVIEW", "Buyer approved in PayPal", "PayPal reports the order as approved by the buyer."),
    ("PAYEE", "PRE_CAPTURE", "BLOCK", "Right payee", "The payee on the PayPal order is the merchant recorded when the order was created."),
    ("ORDER_CURRENCY", "PRE_CAPTURE", "REAUTHORISE", "Order currency unchanged", "The PayPal order is in the quote's currency."),
    ("ORDER_AMOUNT", "PRE_CAPTURE", "REAUTHORISE", "Order total unchanged", "The PayPal order total equals the quote the buyer approved."),
    ("ORDER_ITEMS", "PRE_CAPTURE", "REAUTHORISE", "Order items unchanged", "One purchase unit with the approved product, quantity, unit price and checkout reference."),
    ("NOT_ALREADY_CAPTURED", "PRE_CAPTURE", "BLOCK", "Not captured twice", "PayPal holds no capture for this order yet."),
    ("ENGINE_AVAILABLE", "ANY", "REVIEW", "Check completed", "The evaluation itself finished. If the engine fails, the purchase is never allowed."),
)
RULE_TITLES = {r[0]: r[3] for r in RULES}
# How a failure reads to a merchant ("why was this stopped?").
RULE_FAILS = {
    "MANDATE_ACTIVE": "Mandate not active", "PRODUCT_CATEGORY": "Wrong kind of product", "PRODUCT_CONDITION": "Wrong condition",
    "SUBSTITUTION": "Unapproved substitute", "QUANTITY": "Wrong quantity", "APPROVED_SELLER": "Seller not approved",
    "MERCHANT_CHECKOUT_ELIGIBLE": "Not payable through this store", "AVAILABILITY": "Availability unknown", "CURRENCY": "Wrong currency",
    "MAXIMUM_TOTAL": "Total over budget or unknown", "QUOTE_FRESH": "Quote expired", "ORDER_ID": "Different PayPal order",
    "ORDER_APPROVED_BY_BUYER": "Not approved in PayPal", "PAYEE": "Wrong payee", "ORDER_CURRENCY": "Order currency changed",
    "ORDER_AMOUNT": "Order total changed", "ORDER_ITEMS": "Order items changed", "NOT_ALREADY_CAPTURED": "Already captured",
    "ENGINE_AVAILABLE": "Check could not complete",
}
SPEC_NAMES = {"RAM_GB": "memory", "STORAGE_GB": "storage", "SCREEN_IN_TENTHS": "screen size", "BATTERY_HOURS": "battery life", "NOISE_CANCELLING": "noise cancelling"}


def fail_phrase(rule_id: str) -> str:
    if rule_id.startswith("SPEC_"):
        name = rule_id[5:].removesuffix("_MIN").removesuffix("_MAX")
        return f"Must-have not met: {SPEC_NAMES.get(name, name.replace('_', ' ').lower())}"
    return RULE_FAILS.get(rule_id, rule_id)


def rule_key(rule_id: str) -> str:
    """Map a reported rule id to its register entry (SPEC_RAM_GB_MIN -> SPEC_*)."""
    return "SPEC_*" if rule_id.startswith("SPEC_") else rule_id
PRECEDENCE = (Decision.BLOCK, Decision.REAUTHORISE, Decision.REVIEW)
APPROVED_ORDER_STATUS = "APPROVED"


class _Checks:
    def __init__(self) -> None:
        self.items: list[PolicyCheck] = []

    def add(self, rule_id: str, ok: bool | None, on_fail: Decision, expected, observed, source: str, reason: str) -> None:
        """ok=None means the rule could not be evaluated (UNKNOWN), which always leads to REVIEW."""
        status = CheckStatus.UNKNOWN if ok is None else (CheckStatus.PASS if ok else CheckStatus.FAIL)
        self.items.append(
            PolicyCheck(
                rule_id=rule_id,
                status=status,
                on_fail=Decision.REVIEW if ok is None else on_fail,
                expected=str(expected),
                observed=str(observed),
                source=source,
                reason=reason,
            )
        )


def _same_text(a, b) -> bool:
    return str(a).strip().lower() == str(b).strip().lower()


def _spec_checks(c: _Checks, mandate: MandateSpec, offer: OfferFacts) -> None:
    src = f"catalogue:{offer.product_id}"
    for key, wanted in sorted(mandate.product.requirements.items()):
        rule = f"SPEC_{key.upper()}"
        if key.endswith("_min") or key.endswith("_max"):
            attr, is_min = key[:-4], key.endswith("_min")
            got = offer.attributes.get(attr)
            word = "at least" if is_min else "at most"
            if got is None or isinstance(got, (bool, str)) or isinstance(wanted, (bool, str)):
                c.add(rule, None, Decision.REVIEW, f"{attr} {word} {wanted}", "not stated", src,
                      f"The catalogue does not state {attr}, so this requirement cannot be checked.")  # fmt: skip
                continue
            ok = got >= wanted if is_min else got <= wanted
            c.add(rule, ok, Decision.BLOCK, f"{attr} {word} {wanted}", got, src,
                  f"{attr} is {got}; the mandate requires {word} {wanted}.")  # fmt: skip
        else:
            got = offer.attributes.get(key)
            if got is None:
                c.add(rule, None, Decision.REVIEW, f"{key} = {wanted}", "not stated", src,
                      f"The catalogue does not state {key}, so this requirement cannot be checked.")  # fmt: skip
                continue
            c.add(rule, _same_text(got, wanted), Decision.BLOCK, f"{key} = {wanted}", got, src,
                  f"{key} is {got}; the mandate requires {wanted}.")  # fmt: skip


def _pre_order_checks(c: _Checks, mandate: MandateSpec, state: MandateState, offer: OfferFacts, quote: QuoteFacts, now: datetime) -> None:
    msrc = f"mandate:{state.mandate_id}:v{state.version}"
    osrc = f"catalogue:{offer.product_id}"
    qsrc = f"quote:{quote.quote_id}"
    cur = mandate.currency

    active = state.status == "CONFIRMED" and state.is_current_version and now < mandate.expires_at
    why = (
        "The mandate is confirmed, current and unexpired."
        if active
        else "The mandate is not confirmed, has been replaced by a newer version, was revoked, or has expired."
    )
    c.add("MANDATE_ACTIVE", active, Decision.BLOCK, "confirmed, current version, unexpired",
          f"status {state.status}, current {state.is_current_version}, expires {mandate.expires_at:%Y-%m-%d %H:%M}Z", msrc, why)  # fmt: skip

    c.add("PRODUCT_CATEGORY", _same_text(offer.category, mandate.product.category), Decision.BLOCK,
          mandate.product.category, offer.category, osrc, f"The product is a {offer.category}; the mandate is for a {mandate.product.category}.")  # fmt: skip
    c.add("PRODUCT_CONDITION", _same_text(offer.condition, mandate.product.condition.value), Decision.BLOCK,
          mandate.product.condition.value, offer.condition, osrc, f"The product is {offer.condition}; the mandate requires {mandate.product.condition.value}.")  # fmt: skip
    _spec_checks(c, mandate, offer)

    if mandate.product.model:
        same = _same_text(offer.attributes.get("model", offer.title), mandate.product.model)
        ok = same or mandate.substitution.allowed
        reason = (
            "The product is the model the buyer named." if same
            else "A different model is proposed and the mandate allows substitutions." if ok
            else "A different model is proposed and the mandate does not allow substitutions; the buyer must approve it."
        )  # fmt: skip
        c.add("SUBSTITUTION", ok, Decision.REAUTHORISE, mandate.product.model, offer.attributes.get("model", offer.title), osrc, reason)

    c.add("QUANTITY", quote.quantity == mandate.product.quantity, Decision.REAUTHORISE, mandate.product.quantity, quote.quantity, qsrc,
          f"The quote is for {quote.quantity}; the mandate is for {mandate.product.quantity}.")  # fmt: skip

    if mandate.seller.mode == "allowlist":
        ok = offer.seller_id in mandate.seller.approved_seller_ids
        c.add("APPROVED_SELLER", ok, Decision.BLOCK, ", ".join(mandate.seller.approved_seller_ids), offer.seller_id, osrc,
              f"{offer.seller_name} ({offer.seller_id}) is {'on' if ok else 'not on'} the buyer's approved seller list.")  # fmt: skip
    else:
        c.add("APPROVED_SELLER", True, Decision.BLOCK, "any seller", offer.seller_id, osrc, "The buyer accepts any seller.")

    c.add("MERCHANT_CHECKOUT_ELIGIBLE", offer.merchant_checkout_eligible, Decision.BLOCK, "sold through this merchant's checkout",
          "eligible" if offer.merchant_checkout_eligible else "not eligible", osrc,
          "This merchant can take payment for the product." if offer.merchant_checkout_eligible
          else "This merchant is not authorised to take payment for this product.")  # fmt: skip

    in_stock = offer.availability_status == "in_stock"
    c.add("AVAILABILITY", True if in_stock else None, Decision.REVIEW, "in_stock", offer.availability_status, osrc,
          "The product is in stock." if in_stock else "Availability could not be confirmed.")  # fmt: skip

    c.add("CURRENCY", quote.currency == cur, Decision.REAUTHORISE, cur, quote.currency, qsrc,
          f"The quote is in {quote.currency}; the mandate is in {cur}.")  # fmt: skip

    items = quote.unit_amount_minor * quote.quantity
    counted, unknown = items, []
    if mandate.spending.include_shipping:
        if quote.shipping_amount_minor is None:
            unknown.append("shipping")
        else:
            counted += quote.shipping_amount_minor
    if mandate.spending.include_tax:
        if quote.tax_amount_minor is None:
            unknown.append("tax")
        else:
            counted += quote.tax_amount_minor
    parts = "items" + (" + shipping" if mandate.spending.include_shipping else "") + (" + tax" if mandate.spending.include_tax else "")
    limit = display(mandate.spending.maximum_total_minor, cur)
    if unknown:
        c.add("MAXIMUM_TOTAL", None, Decision.REVIEW, f"at most {limit} ({parts})", f"{' and '.join(unknown)} unknown", qsrc,
              f"The budget includes {' and '.join(unknown)}, which the catalogue does not state. It is not assumed to be zero.")  # fmt: skip
    else:
        ok = counted <= mandate.spending.maximum_total_minor
        c.add("MAXIMUM_TOTAL", ok, Decision.BLOCK, f"at most {limit} ({parts})", display(counted, quote.currency), qsrc,
              f"The total counted against the budget is {display(counted, quote.currency)}; the limit is {limit}.")  # fmt: skip

    fresh = now < quote.expires_at
    c.add("QUOTE_FRESH", True if fresh else None, Decision.REVIEW, "quote not expired", f"expires {quote.expires_at:%Y-%m-%d %H:%M}Z", qsrc,
          "The quote is still valid." if fresh else "The quote has expired and must be refreshed.")  # fmt: skip


def _order_checks(c: _Checks, quote: QuoteFacts, order: OrderFacts, expected: ExpectedOrder) -> None:
    src = f"paypal_order:{order.order_id}"
    c.add("ORDER_ID", order.order_id == expected.order_id, Decision.BLOCK, expected.order_id, order.order_id, src,
          "The order returned by PayPal is the one this checkout created." if order.order_id == expected.order_id
          else "PayPal returned a different order from the one this checkout created.")  # fmt: skip

    approved = order.status == APPROVED_ORDER_STATUS
    c.add("ORDER_APPROVED_BY_BUYER", True if approved else None, Decision.REVIEW, APPROVED_ORDER_STATUS, order.status, src,
          "The buyer approved the order in PayPal." if approved else f"PayPal reports the order as {order.status}, not approved by the buyer.")  # fmt: skip

    if expected.payee_merchant_id or expected.payee_email:
        ok = (not expected.payee_merchant_id or order.payee_merchant_id == expected.payee_merchant_id) and (
            not expected.payee_email or _same_text(order.payee_email or "", expected.payee_email)
        )
        c.add("PAYEE", ok, Decision.BLOCK, expected.payee_merchant_id or expected.payee_email, order.payee_merchant_id or order.payee_email or "none", src,
              "The payee is the configured merchant." if ok else "The payee on the PayPal order is not the configured merchant.")  # fmt: skip
    else:
        c.add("PAYEE", None, Decision.REVIEW, "configured merchant", order.payee_merchant_id or "none", src,
              "No expected payee was recorded for this order, so the payee cannot be verified.")  # fmt: skip

    c.add("ORDER_CURRENCY", order.currency == quote.currency, Decision.REAUTHORISE, quote.currency, order.currency, src,
          f"The PayPal order is in {order.currency}; the approved quote is in {quote.currency}.")  # fmt: skip

    if quote.total_amount_minor is None:
        c.add("ORDER_AMOUNT", None, Decision.REVIEW, "quoted total", display(order.total_minor, order.currency), src,
              "The stored quote has no total, so the order amount cannot be verified.")  # fmt: skip
    else:
        ok = order.total_minor == quote.total_amount_minor
        c.add("ORDER_AMOUNT", ok, Decision.REAUTHORISE, display(quote.total_amount_minor, quote.currency), display(order.total_minor, order.currency), src,
              "The PayPal order total equals the quote the buyer approved." if ok
              else "The PayPal order total differs from the quote the buyer approved.")  # fmt: skip

    item = order.items[0] if len(order.items) == 1 else None
    ok = (
        order.purchase_unit_count == 1
        and item is not None
        and item.sku == expected.sku
        and item.quantity == quote.quantity
        and item.unit_amount_minor == quote.unit_amount_minor
        and order.custom_id == expected.custom_id
    )
    observed = f"{order.purchase_unit_count} unit(s), " + (f"sku {item.sku} x{item.quantity} at {display(item.unit_amount_minor, order.currency)}" if item else f"{len(order.items)} item line(s)")
    c.add("ORDER_ITEMS", ok, Decision.REAUTHORISE, f"1 unit, sku {expected.sku} x{quote.quantity} at {display(quote.unit_amount_minor, quote.currency)}", observed, src,
          "The line item on the PayPal order matches the approved purchase." if ok
          else "The line item or reference on the PayPal order differs from the approved purchase.")  # fmt: skip

    c.add("NOT_ALREADY_CAPTURED", not order.has_capture, Decision.BLOCK, "no capture yet", "captured" if order.has_capture else "no capture", src,
          "No capture exists for this order." if not order.has_capture else "PayPal already holds a capture for this order.")  # fmt: skip


def decide(checks: list[PolicyCheck]) -> Decision:
    fired = {ch.on_fail for ch in checks if ch.status is not CheckStatus.PASS}
    for decision in PRECEDENCE:
        if decision in fired:
            return decision
    return Decision.ALLOW


def evaluate(
    *,
    mandate: MandateSpec,
    state: MandateState,
    offer: OfferFacts,
    quote: QuoteFacts,
    now: datetime,
    order: OrderFacts | None = None,
    expected: ExpectedOrder | None = None,
) -> Evaluation:
    """Evaluate a proposed purchase. Pass `order` and `expected` for the pre-capture evaluation."""
    c = _Checks()
    _pre_order_checks(c, mandate, state, offer, quote, now)
    stage = "PRE_ORDER"
    if order is not None:
        if expected is None:
            raise ValueError("expected is required when order is given")
        stage = "PRE_CAPTURE"
        _order_checks(c, quote, order, expected)
    decision = decide(c.items)
    return Evaluation(
        policy_version=POLICY_VERSION,
        stage=stage,
        decision=decision,
        checks=c.items,
        failed_constraints=[ch.rule_id for ch in c.items if ch.status is not CheckStatus.PASS],
        requires_buyer_reapproval=decision is Decision.REAUTHORISE,
    )


def fail_closed(stage: str, reason: str) -> Evaluation:
    """The evaluation returned when the engine itself could not run. Never ALLOW."""
    check = PolicyCheck(rule_id="ENGINE_AVAILABLE", status=CheckStatus.UNKNOWN, on_fail=Decision.REVIEW,
                        expected="evaluation completes", observed="evaluation failed", source="engine", reason=reason)  # fmt: skip
    return Evaluation(policy_version=POLICY_VERSION, stage=stage, decision=Decision.REVIEW, checks=[check],
                      failed_constraints=["ENGINE_AVAILABLE"], requires_buyer_reapproval=False)  # fmt: skip
