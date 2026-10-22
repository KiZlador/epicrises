from statistics import mean, median

from epicrises.shared.field_schema import KEYS, NA, RANGES


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
