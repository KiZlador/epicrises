import io
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app
from domain.config import Settings
from extraction.pipeline import Pipeline


class IncrementalApiContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pipeline = Pipeline(Settings(llm_enabled=False))
        self.app = self.application(self.pipeline)
        self.client = self.app.test_client()

    def application(self, pipeline):
        app = create_app(pipeline=pipeline, data_dir=self.root)
        app.testing = True
        self.addCleanup(app.extensions["jobs"].shutdown)
        return app

    def upload(self, name):
        response = self.client.post("/upload", data={"files": (io.BytesIO(name.encode()), name)})
        self.assertEqual(response.status_code, 200)

    def process(self):
        response = self.client.post("/process")
        self.assertIn(response.status_code, (200, 202))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.client.get("/process/status").get_json()
            if state["status"] not in {"queued", "running"}:
                return state
            time.sleep(0.005)
        self.fail("Processing did not finish")

    def test_upload_after_completed_batch_processes_only_new_files(self):
        with patch.object(self.pipeline, "process", wraps=self.pipeline.process) as process:
            self.upload("first.md")
            self.assertEqual(self.process()["succeeded"], 1)
            original = {
                path: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.root.glob("*/results/first.md/*.json")
            }
            self.assertEqual(len(original), 3)
            self.upload("second.md")
            self.assertEqual(self.client.get("/process/status").get_json()["status"], "idle")
            state = self.process()
            self.assertEqual((state["total"], state["skipped"], state["succeeded"]), (1, 1, 1))
            self.assertEqual(
                [call.args[0] for call in process.call_args_list], ["first.md", "second.md"]
            )
            for path, snapshot in original.items():
                self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), snapshot)
            self.assertTrue(
                all(item["processed"] for item in self.client.get("/files").json["files"])
            )

    def test_noop_does_not_require_available_model(self):
        self.upload("first.md")
        self.process()
        with patch.object(self.pipeline, "prepare", side_effect=RuntimeError("model unavailable")):
            response = self.client.post("/process")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "done")
        self.assertEqual(response.json["total"], 0)
        self.assertEqual(response.json["skipped"], 1)

    def test_restart_keeps_completed_documents_and_session_access(self):
        self.upload("first.md")
        self.process()
        with self.client.session_transaction() as session:
            identifier = session["id"]
        self.app.extensions["jobs"].shutdown()
        pipeline = Pipeline(Settings(llm_enabled=False))
        restarted = self.application(pipeline)
        self.assertEqual(self.app.secret_key, restarted.secret_key)
        self.client = restarted.test_client()
        with self.client.session_transaction() as session:
            session["id"] = identifier
        self.upload("second.md")
        with patch.object(pipeline, "process", wraps=pipeline.process) as process:
            state = self.process()
        self.assertEqual([call.args[0] for call in process.call_args_list], ["second.md"])
        self.assertEqual(state["skipped"], 1)
        self.assertEqual(self.client.get("/result/first.md").status_code, 200)

    def test_result_without_sidecars_stays_pending_and_source_remains_available(self):
        self.upload("first.md")
        self.process()
        next(self.root.glob("*/results/first.md/evidence.json")).unlink()
        self.assertFalse(self.client.get("/files").json["files"][0]["processed"])
        self.assertEqual(self.client.get("/result/first.md").status_code, 404)
        self.assertEqual(
            self.client.get("/source/first.md").json, {"text": "first.md", "citations": {}}
        )


if __name__ == "__main__":
    unittest.main()
