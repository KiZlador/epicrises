import json
from pathlib import Path

from domain.files import read_document, write_json
from domain.validation import validate_result
from extraction.evidence import build_evidence
from extraction.llm import LocalModel
from extraction.regex.engine import extract_document


def add_evidence(paths: list[Path], results: Path, model: LocalModel | None) -> int:
    failed = 0
    for path in paths:
        destination = results / (path.stem + ".ev.json")
        try:
            destination.unlink(missing_ok=True)
            result = json.loads((results / (path.stem + ".json")).read_text(encoding="utf-8"))
            validate_result(result)
            raw = read_document(path)
            write_json(destination, build_evidence(raw, result, extract_document(raw), model))
            print(f"{path.name}: цитаты сохранены")
        except Exception as exc:
            failed += 1
            print(f"{path.name}: {exc}")
    return 1 if failed else 0
