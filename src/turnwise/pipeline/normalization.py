"""Deterministic normalization of provider-selected source candidates."""

import re
from decimal import Decimal

from turnwise.contracts import ValueCandidate


_CURRENCY_SUFFIX = re.compile(
    r"\s+(?P<currency>U\.S\.\s+dollars?|US\s+dollars?|USD|"
    r"dollars?|pounds?|GBP|euros?|EUR|CAD|AUD)$",
    re.IGNORECASE,
)
_CURRENCY_PREFIX = re.compile(r"^(?P<currency>US\$|USD|\$)\s*", re.IGNORECASE)
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _currency_code(value: str) -> str | None:
    normalized = value.casefold().replace(" ", "")
    if normalized in {"usd", "us$", "$", "u.s.dollars", "u.s.dollar", "usdollars", "usdollar"}:
        return "USD"
    if normalized in {"gbp", "pounds", "pound"}:
        return "GBP"
    if normalized in {"eur", "euros", "euro"}:
        return "EUR"
    if normalized == "cad":
        return "CAD"
    if normalized == "aud":
        return "AUD"
    return None


def _parse_number_words(value: str) -> int:
    total = 0
    current = 0
    for word in re.split(r"[\s-]+", value.casefold()):
        if word in {"and", "a"}:
            continue
        if word in _NUMBER_WORDS:
            current += _NUMBER_WORDS[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        elif word in {"thousand", "million"}:
            scale = 1000 if word == "thousand" else 1_000_000
            total += max(current, 1) * scale
            current = 0
        else:
            raise ValueError(f"unsupported number word {word!r} in candidate")
    return total + current


def normalize_candidate(candidate: ValueCandidate) -> str | dict[str, int | float | str | None]:
    """Normalize a selected candidate while retaining its source evidence elsewhere."""
    if candidate.field_id in {"appliance", "location"}:
        return candidate.text.strip().capitalize()
    if candidate.field_id == "preferred_appointment":
        return candidate.text.strip()
    if candidate.field_id != "spending_limit":
        raise ValueError(f"no candidate normalizer for {candidate.field_id!r}")

    source = candidate.text.strip()
    suffix = _CURRENCY_SUFFIX.search(source)
    prefix = _CURRENCY_PREFIX.match(source)
    if suffix:
        currency_text = suffix.group("currency")
        amount_text = source[: suffix.start()].strip()
    elif prefix:
        currency_text = prefix.group("currency")
        amount_text = source[prefix.end() :].strip()
    else:
        currency_text = ""
        amount_text = source

    if re.fullmatch(r"\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?", amount_text):
        amount_decimal = Decimal(amount_text.replace(",", ""))
        amount: int | float = (
            int(amount_decimal)
            if amount_decimal == amount_decimal.to_integral_value()
            else float(amount_decimal)
        )
    else:
        amount = _parse_number_words(amount_text)
    return {"amount": amount, "currency": _currency_code(currency_text)}