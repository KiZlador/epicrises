import re
from dataclasses import dataclass
from time import perf_counter

from domain.config import Settings
from domain.schema import NA, RANGES
from domain.validation import BINARY, valid_value, validate_result

from .evidence import build_evidence
from .llm import LocalModel
from .regex.core import Hit
from .regex.engine import cross_checks, extract_document, to_result
from .regex.medication import DRUGS
from .statistics import analyze


@dataclass
class Extraction:
    result: dict
    evidence: dict | None
    report: dict


class Pipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = LocalModel(settings) if settings.llm_enabled else None

    def prepare(self):
        if self.model:
            self.model.ensure_configured()

    def process(self, raw: str, *, citations: bool = False) -> Extraction:
        self.prepare()
        started = perf_counter()
        hits = extract_document(raw)
        for key, hit in hits.items():
            if key in RANGES:
                hit.value = str(hit.value).replace(",", ".")
            if not valid_value(key, hit.value):
                replacement = (
                    "0"
                    if key in BINARY
                    else {"type_acs": "NA", "mi_localisation": "N", "ca_fact": "N"}.get(key, NA)
                )
                hits[key] = Hit(
                    replacement,
                    "",
                    "invalid-regex-value",
                    "low",
                    hit.warn + ["Значение не соответствует формату поля"],
                )
        regex_end = perf_counter()
        analysis = analyze(hits)
        stats_end = perf_counter()
        final = {
            key: Hit(hit.value, hit.ev, hit.method, hit.conf, list(hit.warn))
            for key, hit in hits.items()
        }
        changes, warnings = {}, []
        if self.model:
            flat = {key: hit.value for key, hit in hits.items()}
            fields = analysis["review_fields"]
            answer = self.model.review(raw, fields, flat, analysis)
            for key in fields:
                value = answer.get(key)
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
                    classes = {
                        name for name, pattern in DRUGS.items() if re.search(pattern, value, re.I)
                    }
                    if classes and key not in classes:
                        warnings.append(
                            f"{key}: модель указала препарат другого класса; сохранён результат правил"
                        )
                        continue
                if value != hits[key].value:
                    changes[key] = {"before": hits[key].value, "after": value}
                    final[key] = Hit(value, "", "llm", "unverified")
        cross_checks(final)
        result = to_result(final)
        validate_result(result)
        llm_end = perf_counter()
        evidence = None
        if citations:
            try:
                evidence = build_evidence(raw, result, hits, self.model)
            except Exception as exc:
                evidence = build_evidence(raw, result, hits)
                warnings.append(
                    f"Поиск цитат моделью не завершён: {exc}. Сохранены цитаты регулярных правил."
                )
        finished = perf_counter()
        for key, hit in hits.items():
            warnings.extend(f"{key}: {warning}" for warning in hit.warn)
        return Extraction(
            result,
            evidence,
            {
                "mode": "regex-statistics-llm" if self.model else "regex-statistics",
                "seconds": {
                    "regex": regex_end - started,
                    "statistics": stats_end - regex_end,
                    "llm_and_validation": llm_end - stats_end,
                    "citations": finished - llm_end,
                    "total": finished - started,
                },
                "analysis": analysis,
                "changes": changes,
                "warnings": warnings,
            },
        )
