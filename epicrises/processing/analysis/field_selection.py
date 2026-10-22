from collections import Counter

from epicrises.shared.field_schema import KEYS, NA

from .consistency_checks import check_medical_consistency

CONTEXT_FIELDS = {
    "rg_pc",
    "ca_date",
    "dm",
    "hf",
    "ckd",
    "killip",
    "mi_localisation",
    "bp",
    "bpm",
    "smoking",
    "aspirin",
    "2_aag",
    "bb",
    "ace_ing_sartan",
    "statin",
}


def analyze(hits: dict) -> dict:
    suspicious, rules = check_medical_consistency(hits)
    selected = set(suspicious)
    for key, hit in hits.items():
        if hit.warn or hit.conf == "low":
            selected.add(key)
        if key in CONTEXT_FIELDS and hit.value == NA:
            selected.add(key)
    return {
        "review_fields": [key for key in KEYS if key in selected],
        "triggered_rules": rules,
        "missing_count": sum(hit.value == NA for hit in hits.values()),
        "confidence_counts": dict(Counter(hit.conf for hit in hits.values())),
    }
