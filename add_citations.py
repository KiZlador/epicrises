"""Добавление цитат к готовым результатам без изменения значений."""

import argparse

from cli.citations import add_evidence
from cli.config import add_model_arguments, model_settings
from domain.config import resolve_path
from domain.files import documents
from extraction.llm import LocalModel


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="test_docs")
    parser.add_argument("--results", default="test_json")
    add_model_arguments(parser)
    args = parser.parse_args()
    try:
        settings = model_settings(args)
        paths = documents(resolve_path(args.input))
        model = LocalModel(settings) if settings.llm_enabled else None
        if model:
            model.ensure_configured()
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    return add_evidence(paths, resolve_path(args.results), model)


if __name__ == "__main__":
    raise SystemExit(main())
