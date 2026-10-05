"""Консольное извлечение полей без цитат."""

import argparse
from dataclasses import replace
from time import perf_counter

from dotenv import load_dotenv

from domain.config import ROOT, Settings, resolve_path
from domain.files import documents, read_document, write_json
from extraction.pipeline import Pipeline
from extraction.statistics import summarize


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="test_docs", help="Каталог с .md")
    parser.add_argument("--output", default="test_json", help="Каталог результатов")
    parser.add_argument("--metrics", default="reports/benchmark.json")
    parser.add_argument("--model", help="Путь к GGUF; переопределяет MODEL_PATH")
    parser.add_argument("--regex-only", action="store_true", help="Явный запуск без LLM")
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.model:
        settings = replace(settings, model_path=args.model)
    if args.regex_only:
        settings = replace(settings, llm_enabled=False)
    output = resolve_path(args.output)
    metrics = resolve_path(args.metrics)
    try:
        paths = documents(resolve_path(args.input))
        if metrics.parent.resolve() == output.resolve():
            raise ValueError("Метрики должны храниться отдельно от JSON для кейсодателя")
        pipeline = Pipeline(settings)
        pipeline.prepare()
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    started = perf_counter()
    records, results = [], []
    interrupted = False
    for index, path in enumerate(paths, 1):
        destination = output / (path.stem + ".json")
        tick = perf_counter()
        try:
            destination.unlink(missing_ok=True)
            (output / (path.stem + ".ev.json")).unlink(missing_ok=True)
            extraction = pipeline.process(read_document(path))
            write_json(destination, extraction.result)
            results.append(extraction.result)
            record = {"file": path.name, "status": "ok", **extraction.report}
        except Exception as exc:
            record = {"file": path.name, "status": "error", "error": str(exc)}
        except KeyboardInterrupt:
            interrupted = True
            record = {"file": path.name, "status": "interrupted"}
        record["elapsed_seconds"] = perf_counter() - tick
        records.append(record)
        print(
            f"[{index}/{len(paths)}] {path.name}: {record['status']} ({record['elapsed_seconds']:.2f} с)",
            flush=True,
        )
        if interrupted:
            break
    total = perf_counter() - started
    successful = [r["elapsed_seconds"] for r in records if r["status"] == "ok"]
    report = {
        "mode": "regex-statistics-llm" if settings.llm_enabled else "regex-statistics",
        "documents": len(paths),
        "attempted": len(records),
        "pending": len(paths) - len(records),
        "interrupted": interrupted,
        "succeeded": len(results),
        "failed": sum(record["status"] == "error" for record in records),
        "total_seconds": total,
        "average_seconds_per_document": total / len(records),
        "average_successful_document_seconds": sum(successful) / len(successful)
        if successful
        else None,
        "includes_model_loading": settings.llm_enabled,
        "records": records,
        "statistics": summarize(results),
    }
    write_json(metrics, report)
    print(
        f"Всего: {total:.2f} с; среднее: {total / len(records):.2f} с/документ. Метрики: {metrics}"
    )
    return 130 if interrupted else (1 if report["failed"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
