"""Run rule extraction, statistical checks, model review and citation lookup."""

from time import perf_counter

from epicrises.shared.field_validation import validate_result
from epicrises.shared.settings import Settings

from .analysis.field_selection import analyze
from .citations.evidence import build_evidence
from .inference.local_model import LocalModel
from .inference.response_review import apply_review
from .processing_types import Extraction
from .rules.engine import cross_checks, extract_document, to_result
from .rules.normalization import normalize_hits


class DocumentProcessor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = LocalModel(settings) if settings.llm_enabled else None

    def prepare(self):
        if self.model:
            self.model.ensure_configured()

    def process(self, raw: str, *, citations: bool = False) -> Extraction:
        self.prepare()
        started = perf_counter()
        hits = normalize_hits(extract_document(raw))
        regex_end = perf_counter()
        analysis = analyze(hits)
        stats_end = perf_counter()
        fields, answer = [], {}
        if self.model:
            flat = {key: hit.value for key, hit in hits.items()}
            fields = analysis["review_fields"]
            answer = self.model.review(raw, fields, flat, analysis)
        final, changes, warnings = apply_review(hits, answer, fields)
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
