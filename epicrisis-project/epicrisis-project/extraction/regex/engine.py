from datetime import datetime

from domain.schema import GROUPS, KEYS, NA, RANGES

from . import (
    coronary,
    dates,
    diagnoses,
    ecg,
    echo,
    examination,
    laboratory,
    medication,
    radiography,
)
from .core import EXTRACTORS, Hit, in_range
from .document import Doc


def validate(key: str, h: Hit) -> Hit:
    if h.value != NA and key in RANGES and (not in_range(key, h.value)):
        h.warn.append(f"значение {h.value} вне диапазона {RANGES[key]}")
        return Hit(NA, h.ev, "range-reject", "low", h.warn)
    return h


def cross_checks(hits: dict) -> None:
    if hits["ca_fact"].value != "Y":
        for k in ("ca_date", "ca_lad", "rca"):
            if hits[k].value != NA:
                hits[k].warn.append("КАГ не выполнена -> поле обнулено")
            hits[k] = Hit(NA, "", "ca_fact!=Y")
    a, b = (hits["admission_date"].value, hits["discharge_date"].value)
    if a != NA and b != NA:
        try:
            da, db = (datetime.strptime(a, "%d.%m.%Y"), datetime.strptime(b, "%d.%m.%Y"))
        except ValueError:
            hits["discharge_date"].warn.append("некорректная дата эпизода")
            hits["discharge_date"].conf = "low"
            return
        if db < da:
            hits["discharge_date"].warn.append("выписка раньше поступления")
            hits["discharge_date"].conf = "low"


def extract_document(raw: str) -> dict:
    d = Doc(raw)
    hits = {}
    for key in KEYS:
        try:
            h = EXTRACTORS[key](d, key)
        except Exception as e:
            h = Hit(NA, "", "error", "none", [f"error: {e!r}"])
        hits[key] = validate(key, h if h is not None else Hit(NA, "", "not-found", "none"))
    cross_checks(hits)
    return hits


def to_result(hits: dict) -> dict:
    return {g: {k: str(hits[k].value) for k in keys} for g, keys in GROUPS.items()}
