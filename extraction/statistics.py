from collections import Counter
from statistics import mean, median

from domain.schema import KEYS, NA, RANGES

from .consistency import check_medical_consistency

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


def summarize(results: list[dict]) -> dict:
    flat = [{k: v for group in r.values() for k, v in group.items()} for r in results]
    numeric = {}
    for key in RANGES:
        values = [float(row[key]) for row in flat if row[key] != NA]
        if values:
            numeric[key] = {
                "count": len(values),
                "mean": mean(values),
                "median": median(values),
                "min": min(values),
                "max": max(values),
            }
    return {
        "documents": len(results),
        "numeric": numeric,
        "missing_by_field": {k: sum(row[k] == NA for row in flat) for k in KEYS},
    }
