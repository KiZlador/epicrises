from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from time import perf_counter
from uuid import uuid4

from domain.files import write_json
from extraction.statistics import summarize


class Jobs:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="extraction")
        self.lock = RLock()
        self.states = {}

    def busy(self, session_id):
        return self.states.get(session_id, {}).get("status") in {"queued", "running"}

    def start(self, session_id, storage):
        with self.lock:
            if self.busy(session_id):
                return dict(self.states[session_id])
            self.pipeline.prepare()
            names = [item["name"] for item in storage.list()]
            if not names:
                raise ValueError("Загрузите документы перед обработкой")
            state = {
                "id": uuid4().hex,
                "status": "queued",
                "total": len(names),
                "completed": 0,
                "succeeded": 0,
                "errors": [],
                "warnings": [],
                "first": None,
                "mode": "regex-statistics-llm" if self.pipeline.model else "regex-statistics",
            }
            self.states[session_id] = state
            self.executor.submit(self._run, session_id, storage, names)
            return dict(state)

    def status(self, session_id):
        with self.lock:
            state = self.states.get(session_id, {"status": "idle"})
            return {
                **state,
                "errors": list(state.get("errors", [])),
                "warnings": list(state.get("warnings", [])),
            }

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
                    extraction = self.pipeline.process(storage.raw(name), citations=True)
                    with self.lock:
                        storage.save(name, extraction)
                        state["succeeded"] += 1
                        state["first"] = state["first"] or name
                        if extraction.report["warnings"]:
                            state["warnings"].append(
                                {"file": name, "messages": extraction.report["warnings"]}
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
            write_json(
                storage.root / "batch-report.json",
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
