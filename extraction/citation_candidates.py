"""Отбирает строки, допустимые как подтверждение значения поля."""

import re

from domain.validation import BINARY

from .regex.core import FAMILY, negated
from .regex.diagnoses import FLAGS
from .regex.engine import extract_document

NEGATIVE_FIELDS = {key: pattern for key, (pattern, _) in FLAGS.items()}
NEGATIVE_FIELDS.update(
    {
        "ecg_avb": r"(?:АВ|AV|атриовентрикулярн\w*)[\s-]*(?:блокад\w*|блок\b)",
        "ecg_elevation": r"(?:элевац\w+|подъ[её]м\w*)\s+(?:сегмента\s+)?ST|ST\s+(?:элевац\w+|подъ[её]м\w*)",
    }
)


def candidate_lines(lines: list[str], values: dict) -> dict:
    candidates = {key: [] for key in values}
    for index, line in enumerate(lines, 1):
        if not line.strip():
            continue
        hits = extract_document(line)
        for key, value in values.items():
            supported = False
            if key in BINARY and value == "0":
                supported = not FAMILY.search(line) and any(
                    negated(line, match) for match in re.finditer(NEGATIVE_FIELDS[key], line, re.I)
                )
            elif key == "type_acs" and value == "NA":
                supported = bool(
                    re.search(
                        r"нестабильн\w+\s+стенокарди\w*|тип\s+ОКС\s+не\s+установлен", line, re.I
                    )
                )
            elif key == "mi_localisation" and value == "N":
                supported = bool(
                    re.search(r"локализаци\w*\s+(?:не\s+уточнен\w*|неизвестн\w*)", line, re.I)
                )
            else:
                hit = hits[key]
                supported = hit.value == value and bool(hit.ev)
                if not supported and len(value) >= 5 and value != "не указано":
                    supported = value.casefold().rstrip(".") in line.casefold()
            if supported:
                candidates[key].append(index)
    return candidates
