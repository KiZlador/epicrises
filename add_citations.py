"""Добавление цитат к готовым результатам без изменения значений."""

import argparse

from cli.arguments import add_model_arguments, model_settings
from cli.citation_writer import add_evidence
from epicrises.processing.inference.local_model import LocalModel
from epicrises.shared.file_io import documents
from epicrises.shared.settings import resolve_path


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
