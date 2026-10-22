"""Accept only valid model corrections and preserve the original rule evidence."""

import re
from dataclasses import replace

from epicrises.shared.field_schema import NA, RANGES
from epicrises.shared.field_validation import valid_value

from ..processing_types import Hit
from ..rules.medication import DRUGS


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
