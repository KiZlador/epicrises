import re
from datetime import datetime

from .schema import GROUPS, NA, RANGES

BINARY = {"art_hyper", "atr_fibril", "copd", "dm", "tlt", "ecg_avb", "ecg_elevation"}
ENUMS = {
    **{k: {"0", "1"} for k in BINARY},
    "type_acs": {"STEMI", "NSTEMI", "NA"},
    "mi_localisation": {"A", "I", "L", "N"},
    "ca_fact": {"Y", "R", "N"},
    "ca_lad": {"0", "1", "2"},
    "rca": {"0", "1", "2"},
    "killip": {"1", "2", "3", "4"},
}
DATES = {"admission_date", "discharge_date", "ca_date", "rg_date"}


def valid_value(key: str, value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if value == NA:
        return key not in BINARY and key not in {"type_acs", "mi_localisation", "ca_fact"}
    if key in ENUMS:
        return value in ENUMS[key]
    if key in DATES:
        try:
            return datetime.strptime(value, "%d.%m.%Y").strftime("%d.%m.%Y") == value
        except ValueError:
            return False
    if key == "bp":
        if not re.fullmatch(r"\d{2,3}/\d{2,3}", value):
            return False
        systolic, diastolic = map(int, value.split("/"))
        return 50 <= systolic <= 280 and 20 <= diastolic <= 180 and systolic > diastolic
    if key in RANGES:
        if not re.fullmatch(r"\d+(?:\.\d+)?", value):
            return False
        lower, upper = RANGES[key]
        return lower <= float(value) <= upper
    return len(value) <= 1000


def validate_result(result: dict) -> None:
    if set(result) != set(GROUPS):
        raise ValueError("Неверный набор групп результата")
    for group, keys in GROUPS.items():
        if not isinstance(result[group], dict) or set(result[group]) != set(keys):
            raise ValueError(f"Неверный набор полей: {group}")
        for key in keys:
            if not valid_value(key, result[group][key]):
                raise ValueError(f"Недопустимое значение поля {key}")
