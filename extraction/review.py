"""Normalize rule output and validate changes proposed by the language model."""

import re
from dataclasses import replace

from domain.schema import NA, RANGES
from domain.validation import BINARY, valid_value

from .regex.core import Hit
from .regex.medication import DRUGS


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


def apply_review(
    hits: dict[str, Hit], answers: dict, fields: list[str]
) -> tuple[dict[str, Hit], dict, list[str]]:
    """Return a reviewed copy, retaining rule values for invalid model answers."""
    reviewed = {key: replace(hit, warn=list(hit.warn)) for key, hit in hits.items()}
    changes, warnings = {}, []
    for key in fields:
        value = answers.get(key)
        if isinstance(value, str):
            value = value.strip()
            if key in RANGES:
                value = value.replace(",", ".")
        if not valid_value(key, value):
            warnings.append(
                f"{key}: модель не вернула допустимое значение; сохранён результат правил"
            )
            continue
        if key in DRUGS and value != NA:
            classes = {name for name, pattern in DRUGS.items() if re.search(pattern, value, re.I)}
            if classes and key not in classes:
                warnings.append(
                    f"{key}: модель указала препарат другого класса; сохранён результат правил"
                )
                continue
        if value != hits[key].value:
            changes[key] = {"before": hits[key].value, "after": value}
            reviewed[key] = Hit(value, "", "llm", "unverified")
    return reviewed, changes, warnings
