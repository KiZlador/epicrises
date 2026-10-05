"""Добавление цитат к готовым результатам без изменения значений."""

import argparse
import json

from dotenv import load_dotenv

from domain.config import ROOT, Settings, resolve_path
from domain.files import documents, read_document, write_json
from domain.validation import validate_result
from extraction.evidence import build_evidence
from extraction.llm import LocalModel
from extraction.regex.engine import extract_document


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="test_docs")
    parser.add_argument("--results", default="test_json")
    parser.add_argument("--regex-only", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    model = LocalModel(settings) if settings.llm_enabled and not args.regex_only else None
    try:
        paths = documents(resolve_path(args.input))
        if model:
            model.ensure_configured()
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    failed = 0
    for path in paths:
        destination = resolve_path(args.results) / (path.stem + ".ev.json")
        try:
            destination.unlink(missing_ok=True)
            result = json.loads(
                (resolve_path(args.results) / (path.stem + ".json")).read_text(encoding="utf-8")
            )
            validate_result(result)
            raw = read_document(path)
            write_json(destination, build_evidence(raw, result, extract_document(raw), model))
            print(f"{path.name}: цитаты сохранены")
        except Exception as exc:
            failed += 1
            print(f"{path.name}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
