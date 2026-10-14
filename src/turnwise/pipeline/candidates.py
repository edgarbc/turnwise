"""Deterministic candidate extraction for appointment and money mentions."""

import re
from collections.abc import Iterable

from turnwise.contracts import TranscriptEvent, ValueCandidate


_WEEKDAY = (
    r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
)
_TIME_WORD = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
_APPOINTMENT_PATTERN = re.compile(
    rf"(?<![A-Za-z])"
    rf"(?:(?:next|this)\s+)?(?:{_WEEKDAY})"
    rf"(?:\s+(?:morning|afternoon|evening|night|noon))?"
    rf"(?:\s+after\s+(?:lunch|breakfast|work))?"
    rf"(?:\s+at\s+(?:\d{{1,2}}(?::\d{{2}})?\s*(?:a\.?m\.?|p\.?m\.?)?|{_TIME_WORD}))?"
    rf"(?![A-Za-z])",
    re.IGNORECASE,
)
_APPLIANCE_TERMS = (
    "washer-dryer combo",
    "mini-split air conditioner",
    "built-in dishwasher",
    "portable dishwasher",
    "electric dryer",
    "gas oven",
    "chest freezer",
    "upright freezer",
    "washing machine",
    "water heater",
    "water softener",
    "air conditioner",
    "garbage disposal",
    "dishwasher",
    "oven",
    "refrigerator",
    "microwave",
    "freezer",
    "furnace",
    "sump pump",
    "range",
    "cooktop",
    "boiler",
    "dehumidifier",
    "wine cooler",
    "ice maker",
    "clothes dryer",
    "dryer",
)
_APPLIANCE_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:"
    + "|".join(re.escape(term) for term in _APPLIANCE_TERMS)
    + r")(?![A-Za-z])",
    re.IGNORECASE,
)
_LOCATION_PATTERN = re.compile(
    r"(?=\b(?:in|at)\s+(?:(?:the|our|my)\s+)?"
    r"(?P<place>[A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,4}))",
    re.IGNORECASE,
)
_LOCATION_STOP_WORDS = {
    "a",
    "and",
    "are",
    "because",
    "but",
    "has",
    "have",
    "is",
    "makes",
    "making",
    "of",
    "that",
    "when",
    "where",
    "which",
    "with",
    "then",
    "ten",
    "eleven",
    "twelve",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}

_NUMBER_WORD = (
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"hundred|thousand|million|and|a"
)
_NUMBER = (
    rf"(?:\d{{1,3}}(?:,\d{{3}})*(?:\.\d{{1,2}})?|"
    rf"(?:{_NUMBER_WORD})(?:[\s-]+(?:{_NUMBER_WORD})){{0,6}})"
)
_MONEY_SUFFIX_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9])(?P<amount>{_NUMBER})\s+"
    r"(?P<currency>U\.S\.\s+dollars?|US\s+dollars?|USD|"
    r"dollars?|pounds?|GBP|euros?|EUR|CAD|AUD)\b",
    re.IGNORECASE,
)
_MONEY_PREFIX_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?P<currency>US\$|USD|\$)\s*"
    r"(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\b",
    re.IGNORECASE,
)


def _candidate(
    event: TranscriptEvent,
    field_id: str,
    start: int,
    end: int,
) -> ValueCandidate:
    return ValueCandidate(
        candidate_id=f"{event.event_id}:{field_id}:{start}:{end}",
        field_id=field_id,
        event_id=event.event_id,
        start_char=start,
        end_char=end,
        text=event.text[start:end],
    )


def extract_candidates(
    events: Iterable[TranscriptEvent],
    *,
    candidate_fields: Iterable[str] = (
        "appliance",
        "location",
        "preferred_appointment",
        "spending_limit",
    ),
) -> tuple[ValueCandidate, ...]:
    """Find appointment and currency mentions in customer events.

    Extraction is deliberately lexical: it returns every matching mention,
    including distractors. Provider inputs can then select among candidates;
    this function does not decide whether a mention answers a task field.
    Offsets are zero-based, half-open Unicode code-point indices.
    """
    enabled_fields = frozenset(candidate_fields)
    event_sequence = tuple(events)
    event_positions = {
        event.event_id: index for index, event in enumerate(event_sequence)
    }
    candidates: list[ValueCandidate] = []

    for event in event_sequence:
        if event.speaker != "customer":
            continue

        if "appliance" in enabled_fields:
            candidates.extend(
                _candidate(event, "appliance", match.start(), match.end())
                for match in _APPLIANCE_PATTERN.finditer(event.text)
            )

        if "location" in enabled_fields:
            appliance_spans = [
                (match.start(), match.end())
                for match in _APPLIANCE_PATTERN.finditer(event.text)
            ]
            for match in _LOCATION_PATTERN.finditer(event.text):
                place = match.group("place")
                words = list(re.finditer(r"\S+", place))
                stop_position = next(
                    (
                        word.start()
                        for word in words
                        if word.group().casefold() in _LOCATION_STOP_WORDS
                    ),
                    len(place),
                )
                normalized_place = place[:stop_position].rstrip(" ,;:")
                if not normalized_place:
                    continue
                start = match.start("place")
                end = start + len(normalized_place)
                if any(start < appliance_end and end > appliance_start for appliance_start, appliance_end in appliance_spans):
                    continue
                candidates.append(
                    _candidate(event, "location", start, end)
                )

        if "preferred_appointment" in enabled_fields:
            candidates.extend(
                _candidate(event, "preferred_appointment", match.start(), match.end())
                for match in _APPOINTMENT_PATTERN.finditer(event.text)
            )

        if "spending_limit" in enabled_fields:
            money_matches = [
                *_MONEY_SUFFIX_PATTERN.finditer(event.text),
                *_MONEY_PREFIX_PATTERN.finditer(event.text),
            ]
            candidates.extend(
                _candidate(event, "spending_limit", match.start(), match.end())
                for match in money_matches
            )

    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                event_positions[item.event_id],
                item.start_char,
                item.field_id,
            ),
        )
    )