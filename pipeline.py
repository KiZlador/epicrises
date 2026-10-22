"""Консольное извлечение полей без цитат."""

import argparse

from cli.batch import run_batch
from cli.config import add_model_arguments, model_settings
from domain.config import resolve_path
from domain.files import documents
from extraction.pipeline import Pipeline


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
        pipeline = Pipeline(settings)
        pipeline.prepare()
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    return run_batch(paths, output, metrics, pipeline, llm_enabled=settings.llm_enabled)


if __name__ == "__main__":
    raise SystemExit(main())
