"""Normalize extracted values before selecting fields for review."""

from dataclasses import replace

from epicrises.shared.field_schema import NA, RANGES
from epicrises.shared.field_validation import BINARY, valid_value

from ..processing_types import Hit


def normalize_hits(hits: dict[str, Hit]) -> dict[str, Hit]:
    normalized = {}
    for key, hit in hits.items():
        value = str(hit.value).replace(",", ".") if key in RANGES else hit.value
        if valid_value(key, value):
            normalized[key] = replace(hit, value=value, warn=list(hit.warn))
            continue
        fallback = (
            "0"
            if key in BINARY
            else {"type_acs": "NA", "mi_localisation": "N", "ca_fact": "N"}.get(key, NA)
        )
        normalized[key] = Hit(
            fallback,
            "",
            "invalid-regex-value",
            "low",
            hit.warn + ["Значение не соответствует формату поля"],
        )
    return normalized
