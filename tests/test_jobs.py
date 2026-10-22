import io
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.jobs import Jobs
from backend.storage import Storage
from domain.schema import GROUPS, NA
from extraction.pipeline import Extraction


class RecordingPipeline:
    model = None

    def __init__(self):
        self.prepare = Mock()
        self.calls = []
        self.failures = set()

    def process(self, raw, *, citations):
        self.calls.append(raw)
        if raw in self.failures:
            raise ValueError(f"Ошибка документа: {raw}")
        return Extraction(
            result={group: dict.fromkeys(keys, NA) for group, keys in GROUPS.items()},
            evidence={"source": raw} if citations else None,
            report={"warnings": [f"Проверить: {raw}"]},
        )


class JobContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = Storage(Path(self.temp.name))
        self.pipeline = RecordingPipeline()
        self.jobs = self.new_jobs(self.pipeline)

    def new_jobs(self, pipeline):
        jobs = Jobs(pipeline)
        self.addCleanup(jobs.shutdown)
        return jobs

    def upload(self, name, text):
        self.storage.upload(
            [SimpleNamespace(filename=name, stream=io.BytesIO(text.encode("utf-8")))]
        )

    def wait(self, jobs=None):
        jobs = jobs or self.jobs
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = jobs.status("session")
            if state["status"] not in {"queued", "running"}:
                return state
            Event().wait(0.01)
        self.fail("Фоновая задача не завершилась")

    def run_batch(self):
        self.jobs.start("session", self.storage)
        state = self.wait()
        self.assertEqual(state["status"], "done", state)
        return state

    def test_new_batch_does_not_touch_processed_documents(self):
        self.upload("first.md", "первый")
        self.run_batch()
        saved = {
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.storage.results.rglob("*")
            if path.is_file()
        }

        self.upload("second.md", "второй")
        state = self.run_batch()

        self.assertEqual(self.pipeline.calls, ["первый", "второй"])
        self.assertEqual(state["total"], 1)
        self.assertEqual(state["skipped"], 1)
        self.assertEqual(state["completed"], 1)
        self.assertEqual(state["succeeded"], 1)
        self.assertEqual(state["first"], "second.md")
        self.assertTrue(saved)
        for path, original in saved.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), original)

    def test_retry_only_processes_failed_documents(self):
        self.upload("first.md", "первый")
        self.upload("second.md", "второй")
        self.pipeline.failures.add("первый")
        failed = self.run_batch()
        self.assertEqual(failed["succeeded"], 1)
        self.assertEqual(
            failed["errors"], [{"file": "first.md", "error": "Ошибка документа: первый"}]
        )

        self.pipeline.failures.clear()
        retried = self.run_batch()
        self.assertEqual(self.pipeline.calls, ["первый", "второй", "первый"])
        self.assertEqual(retried["total"], 1)
        self.assertEqual(retried["skipped"], 1)
        self.assertEqual(retried["errors"], [])
        self.assertTrue(all(item["processed"] for item in self.storage.list()))

    def test_completed_batch_is_noop_without_model_preparation(self):
        self.upload("first.md", "первый")
        self.run_batch()
        report = self.storage.root / "batch-report.json"
        original = (report.read_bytes(), report.stat().st_mtime_ns)
        self.pipeline.prepare.side_effect = RuntimeError("Модель недоступна")

        state = self.jobs.start("session", self.storage)

        self.assertEqual(state["status"], "done")
        self.assertEqual(state["total"], 0)
        self.assertEqual(state["skipped"], 1)
        self.assertEqual(state["completed"], 0)
        self.assertEqual(state["succeeded"], 0)
        self.assertEqual(state["seconds"], 0)
        self.assertIsNone(state["first"])
        self.assertIsNone(state["current"])
        self.assertEqual(self.pipeline.calls, ["первый"])
        self.pipeline.prepare.assert_called_once()
        self.assertEqual((report.read_bytes(), report.stat().st_mtime_ns), original)

    def test_empty_storage_is_rejected_before_model_preparation(self):
        self.pipeline.prepare.side_effect = RuntimeError("Модель недоступна")
        with self.assertRaisesRegex(ValueError, "Загрузите документы"):
            self.jobs.start("session", self.storage)
        self.pipeline.prepare.assert_not_called()
        self.assertEqual(
            self.jobs.status("session"), {"status": "idle", "errors": [], "warnings": []}
        )

    def test_restarted_queue_uses_persisted_completion(self):
        self.upload("first.md", "первый")
        self.run_batch()
        self.jobs.shutdown()
        self.upload("second.md", "второй")

        pipeline = RecordingPipeline()
        restarted = self.new_jobs(pipeline)
        restarted.start("session", Storage(self.storage.root))
        state = self.wait(restarted)

        self.assertEqual(state["status"], "done", state)
        self.assertEqual(pipeline.calls, ["второй"])
        self.assertEqual(state["skipped"], 1)

    def test_status_does_not_expose_mutable_nested_state(self):
        self.upload("first.md", "первый")
        self.upload("second.md", "второй")
        self.pipeline.failures.add("второй")
        state = self.run_batch()
        state["warnings"][0]["messages"].append("внешнее изменение")
        state["errors"][0]["error"] = "внешнее изменение"

        current = self.jobs.status("session")
        self.assertEqual(current["warnings"][0]["messages"], ["Проверить: первый"])
        self.assertEqual(current["errors"][0]["error"], "Ошибка документа: второй")

    def test_running_job_is_reused_and_cannot_be_reset(self):
        self.upload("first.md", "первый")
        entered, release = Event(), Event()
        original = self.pipeline.process

        def delayed(raw, *, citations):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return original(raw, citations=citations)

        with patch.object(self.pipeline, "process", delayed):
            try:
                first = self.jobs.start("session", self.storage)
                self.assertTrue(entered.wait(2))
                second = self.jobs.start("session", self.storage)
                self.assertEqual(first["id"], second["id"])
                second["warnings"].append({"file": "other.md", "messages": []})
                self.assertEqual(self.jobs.status("session")["warnings"], [])
                with self.assertRaisesRegex(RuntimeError, "Дождитесь"):
                    self.jobs.reset("session")
            finally:
                release.set()
                self.wait()
        self.assertEqual(self.pipeline.calls, ["первый"])

    def test_reset_clears_progress_but_keeps_results(self):
        self.upload("first.md", "первый")
        self.run_batch()
        self.jobs.reset("session")
        self.assertEqual(
            self.jobs.status("session"), {"status": "idle", "errors": [], "warnings": []}
        )
        self.assertEqual(self.storage.list(), [{"name": "first.md", "processed": True}])
        self.assertEqual(self.jobs.start("session", self.storage)["total"], 0)

    def test_executor_rejection_does_not_leave_session_busy(self):
        self.upload("first.md", "первый")
        with patch.object(self.jobs.executor, "submit", side_effect=RuntimeError("queue closed")):
            with self.assertRaisesRegex(RuntimeError, "Не удалось запустить"):
                self.jobs.start("session", self.storage)
        self.assertFalse(self.jobs.busy("session"))
        self.assertEqual(self.jobs.status("session")["status"], "failed")
        self.assertEqual(self.storage.list(), [{"name": "first.md", "processed": False}])

        state = self.run_batch()
        self.assertEqual(state["succeeded"], 1)
        self.assertEqual(self.pipeline.calls, ["первый"])

    def test_shutdown_waits_for_results(self):
        self.upload("first.md", "первый")
        self.jobs.start("session", self.storage)
        self.jobs.shutdown()
        self.assertEqual(self.jobs.status("session")["status"], "done")
        self.assertEqual(self.storage.list(), [{"name": "first.md", "processed": True}])


if __name__ == "__main__":
    unittest.main()
