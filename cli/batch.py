from pathlib import Path
from time import perf_counter

from domain.files import read_document, write_json
from extraction.pipeline import Pipeline
from extraction.statistics import summarize


def _process_document(path: Path, output: Path, pipeline: Pipeline) -> tuple[dict, dict | None]:
    destination = output / (path.stem + ".json")
    started = perf_counter()
    result = None
    try:
        destination.unlink(missing_ok=True)
        (output / (path.stem + ".ev.json")).unlink(missing_ok=True)
        extraction = pipeline.process(read_document(path))
        write_json(destination, extraction.result)
        result = extraction.result
        record = {"file": path.name, "status": "ok", **extraction.report}
    except Exception as exc:
        record = {"file": path.name, "status": "error", "error": str(exc)}
    except KeyboardInterrupt:
        record = {"file": path.name, "status": "interrupted"}
    record["elapsed_seconds"] = perf_counter() - started
    return record, result


def _report(
    records: list[dict], results: list[dict], total: int, elapsed: float, mode: str
) -> dict:
    successful = [record["elapsed_seconds"] for record in records if record["status"] == "ok"]
    return {
        "mode": mode,
        "documents": total,
        "attempted": len(records),
        "pending": total - len(records),
        "interrupted": any(record["status"] == "interrupted" for record in records),
        "succeeded": len(results),
        "failed": sum(record["status"] == "error" for record in records),
        "total_seconds": elapsed,
        "average_seconds_per_document": elapsed / len(records) if records else 0,
        "average_successful_document_seconds": sum(successful) / len(successful)
        if successful
        else None,
        "includes_model_loading": mode == "regex-statistics-llm",
        "records": records,
        "statistics": summarize(results),
    }


def run_batch(
    paths: list[Path], output: Path, metrics: Path, pipeline: Pipeline, *, llm_enabled: bool
) -> int:
    started = perf_counter()
    records, results = [], []
    for index, path in enumerate(paths, 1):
        record, result = _process_document(path, output, pipeline)
        records.append(record)
        if result is not None:
            results.append(result)
        print(
            f"[{index}/{len(paths)}] {path.name}: {record['status']} ({record['elapsed_seconds']:.2f} с)",
            flush=True,
        )
        if record["status"] == "interrupted":
            break
    mode = "regex-statistics-llm" if llm_enabled else "regex-statistics"
    report = _report(records, results, len(paths), perf_counter() - started, mode)
    write_json(metrics, report)
    print(
        f"Всего: {report['total_seconds']:.2f} с; "
        f"среднее: {report['average_seconds_per_document']:.2f} с/документ. Метрики: {metrics}"
    )
    return 130 if report["interrupted"] else (1 if report["failed"] else 0)
