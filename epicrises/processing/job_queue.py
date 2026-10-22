from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
from time import perf_counter
from uuid import uuid4

from .analysis.batch_statistics import summarize


class JobQueue:
    """Одна очередь для общей модели; состояние задач хранится до перезапуска."""

    def __init__(self, processor):
        self.processor = processor
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="extraction")
        self.lock = RLock()
        self.states = {}

    def busy(self, session_id):
        with self.lock:
            return self.states.get(session_id, {}).get("status") in {"queued", "running"}

    def reset(self, session_id):
        """Сбрасывает прогресс после изменения документов, сохраняя результаты."""
        with self.lock:
            if self.busy(session_id):
                raise RuntimeError("Дождитесь завершения обработки")
            self.states.pop(session_id, None)

    def start(self, session_id, storage):
        with self.lock:
            if self.busy(session_id):
                return self.status(session_id)

            documents = storage.list()
            if not documents:
                raise ValueError("Загрузите документы перед обработкой")
            names = [item["name"] for item in documents if not item["processed"]]
            if names:
                self.processor.prepare()

            state = {
                "id": uuid4().hex,
                "status": "queued" if names else "done",
                "total": len(names),
                "skipped": len(documents) - len(names),
                "completed": 0,
                "succeeded": 0,
                "errors": [],
                "warnings": [],
                "first": None,
                "current": None,
                "mode": "regex-statistics-llm" if self.processor.model else "regex-statistics",
            }
            self.states[session_id] = state
            if not names:
                state["seconds"] = 0
                return self.status(session_id)

            try:
                self.executor.submit(self._run, session_id, storage, names)
            except Exception as exc:
                state.update(status="failed", error=str(exc))
                raise RuntimeError(f"Не удалось запустить обработку: {exc}") from exc
            return self.status(session_id)

    def status(self, session_id):
        with self.lock:
            state = self.states.get(session_id, {"status": "idle", "errors": [], "warnings": []})
            return deepcopy(state)

    def shutdown(self, wait=True):
        """Завершает очередь; при wait=True ждёт сохранения результатов."""
        self.executor.shutdown(wait=wait)

    def _run(self, session_id, storage, names):
        started = perf_counter()
        results, records = [], []
        with self.lock:
            state = self.states[session_id]
            state["status"] = "running"
        try:
            for name in names:
                try:
                    with self.lock:
                        storage.discard_result(name)
                        state["current"] = name
                    extraction = self.processor.process(storage.raw(name), citations=True)
                    with self.lock:
                        storage.save(name, extraction)
                        state["succeeded"] += 1
                        state["first"] = state["first"] or name
                        if extraction.report["warnings"]:
                            state["warnings"].append(
                                {"file": name, "messages": list(extraction.report["warnings"])}
                            )
                    results.append(extraction.result)
                    records.append({"file": name, **extraction.report})
                except Exception as exc:
                    with self.lock:
                        storage.discard_result(name)
                        state["errors"].append({"file": name, "error": str(exc)})
                finally:
                    with self.lock:
                        state["completed"] += 1

            elapsed = perf_counter() - started
            storage.save_batch_report(
                {
                    "total_seconds": elapsed,
                    "average_seconds_per_document": elapsed / len(names),
                    "records": records,
                    "errors": state["errors"],
                    "statistics": summarize(results),
                },
            )
            with self.lock:
                state.update(status="done", seconds=elapsed, current=None)
        except Exception as exc:
            with self.lock:
                state.update(status="failed", error=str(exc), current=None)
