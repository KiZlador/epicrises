"""Консольное извлечение полей без цитат."""

import argparse

from cli.arguments import add_model_arguments, model_settings
from cli.batch_runner import run_batch
from epicrises.processing import DocumentProcessor
from epicrises.shared.file_io import documents
from epicrises.shared.settings import resolve_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="test_docs", help="Каталог с .md")
    parser.add_argument("--output", default="test_json", help="Каталог результатов")
    parser.add_argument("--metrics", default="reports/benchmark.json")
    add_model_arguments(parser)
    args = parser.parse_args()
    output = resolve_path(args.output)
    metrics = resolve_path(args.metrics)
    try:
        settings = model_settings(args)
        paths = documents(resolve_path(args.input))
        if metrics.parent.resolve() == output.resolve():
            raise ValueError("Метрики должны храниться отдельно от JSON результатов")
        processor = DocumentProcessor(settings)
        processor.prepare()
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    return run_batch(paths, output, metrics, processor, llm_enabled=settings.llm_enabled)


if __name__ == "__main__":
    raise SystemExit(main())
