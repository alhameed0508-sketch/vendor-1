"""Money helpers. Amounts are integers in minor units everywhere; Decimal only at the edges."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ISO 4217 exponents for currencies PayPal supports. Only the configured currency is enabled for checkout.
CURRENCY_EXPONENT = {
    "USD": 2, "EUR": 2, "GBP": 2, "AUD": 2, "CAD": 2, "SGD": 2, "CHF": 2, "NZD": 2, "SEK": 2, "NOK": 2,
    "DKK": 2, "PLN": 2, "MXN": 2, "BRL": 2, "HKD": 2, "JPY": 0, "HUF": 0, "TWD": 0,
}  # fmt: skip


class MoneyError(ValueError):
    pass


def exponent(currency: str) -> int:
    try:
        return CURRENCY_EXPONENT[currency.upper()]
    except KeyError as exc:
        raise MoneyError(f"Unsupported currency: {currency}") from exc


def to_minor(amount: str | int | Decimal, currency: str) -> int:
    """Convert a major-unit amount such as '1000.00' to minor units. Rejects floats and extra precision."""
    if isinstance(amount, float):
        raise MoneyError("Floats are not accepted for money")
    try:
        value = Decimal(str(amount).replace(",", "").strip())
    except InvalidOperation as exc:
        raise MoneyError(f"Not a valid amount: {amount!r}") from exc
    if not value.is_finite() or value < 0:
        raise MoneyError(f"Not a valid amount: {amount!r}")
    scaled = value * (Decimal(10) ** exponent(currency))
    if scaled != scaled.to_integral_value():
        raise MoneyError(f"Too many decimal places for {currency}: {amount!r}")
    return int(scaled)


def to_major(minor: int, currency: str) -> str:
    """Format minor units as the decimal string PayPal expects, e.g. 98600 -> '986.00'."""
    exp = exponent(currency)
    value = (Decimal(int(minor)) / (Decimal(10) ** exp)).quantize(Decimal(1).scaleb(-exp), rounding=ROUND_HALF_UP)
    return f"{value:.{exp}f}"


def display(minor: int | None, currency: str) -> str:
    if minor is None:
        return "unknown"
    whole, _, frac = to_major(minor, currency).partition(".")
    return f"{currency.upper()} {int(whole):,}" + (f".{frac}" if frac else "")
