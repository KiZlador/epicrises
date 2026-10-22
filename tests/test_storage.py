import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from epicrises.documents.document_store import ARTIFACTS, DocumentStore
from epicrises.processing import DocumentProcessor
from epicrises.shared.file_io import write_json
from epicrises.shared.settings import Settings


class StorageContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = DocumentStore(Path(self.temp.name))
        self.extraction = DocumentProcessor(Settings(llm_enabled=False)).process(
            "АД 120/80 мм рт. ст. ЧСС 70 в минуту.", citations=True
        )

    def upload(self, *names):
        incoming = [FileStorage(io.BytesIO(b"document"), name) for name in names]
        return self.storage.upload(incoming)

    def legacy_result(self, name):
        values = (self.extraction.result, self.extraction.evidence, self.extraction.report)
        for suffix, value in zip(ARTIFACTS, values, strict=True):
            write_json(self.storage.results / (Path(name).stem + suffix), value)

    def test_document_names_cannot_collide_with_another_documents_artifacts(self):
        names = ("case.md", "case.ev.md", "case.report.md", "case.json.md")
        self.upload(*names)
        for name in names:
            self.storage.save(name, self.extraction)
        self.assertTrue(all(item["processed"] for item in self.storage.list()))
        self.assertEqual(len(list(self.storage.results.rglob("*.json"))), 12)
        self.storage.delete("case.ev.md")
        for name in ("case.md", "case.report.md", "case.json.md"):
            self.assertEqual(self.storage.read_result(name), self.extraction.result)
            self.assertEqual(self.storage.read_result(name, ".ev.json"), self.extraction.evidence)

    def test_legacy_results_are_read_without_rewriting(self):
        self.upload("case.md")
        self.legacy_result("case.md")
        before = {
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.storage.results.iterdir()
        }
        self.assertTrue(self.storage.is_processed("case.md"))
        self.assertEqual(self.storage.read_result("case.md"), self.extraction.result)
        for path, snapshot in before.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), snapshot)
        self.storage.delete("case.md")
        self.assertEqual(list(self.storage.results.iterdir()), [])

    def test_new_bundle_does_not_conflict_with_legacy_json_filename(self):
        self.upload("case.md", "case.json.md")
        self.legacy_result("case.md")
        self.storage.save("case.json.md", self.extraction)
        self.assertTrue(all(item["processed"] for item in self.storage.list()))
        self.assertEqual(self.storage.read_result("case.md"), self.extraction.result)

    def test_legacy_sidecar_is_not_mistaken_for_a_processed_document(self):
        self.upload("case.md", "case.ev.md")
        self.legacy_result("case.md")
        self.assertFalse(self.storage.is_processed("case.ev.md"))
        self.storage.discard_result("case.ev.md")
        self.assertTrue(self.storage.is_processed("case.md"))
        self.assertEqual(self.storage.read_result("case.md", ".ev.json"), self.extraction.evidence)

    def test_delete_removes_incomplete_legacy_artifacts(self):
        self.upload("case.md")
        write_json(self.storage.results / "case.ev.json", self.extraction.evidence)
        write_json(self.storage.results / "case.report.json", self.extraction.report)
        self.assertFalse(self.storage.is_processed("case.md"))
        self.storage.delete("case.md")
        self.assertEqual(list(self.storage.results.iterdir()), [])

    def test_legacy_report_collision_preserves_other_documents_result_on_delete(self):
        self.upload("case.md", "case.report.md")
        self.legacy_result("case.md")
        self.legacy_result("case.report.md")
        self.assertFalse(self.storage.is_processed("case.md"))
        self.assertTrue(self.storage.is_processed("case.report.md"))
        self.storage.delete("case.md")
        self.assertEqual(self.storage.read_result("case.report.md"), self.extraction.result)
        self.storage.delete("case.report.md")
        self.assertEqual(list(self.storage.results.iterdir()), [])

    def test_partial_save_remains_pending_and_cannot_be_downloaded(self):
        self.upload("case.md")
        original = write_json

        def fail_main_result(path, value):
            if path.name == "result.json":
                raise OSError("disk full")
            original(path, value)

        with patch("epicrises.documents.document_store.write_json", side_effect=fail_main_result):
            with self.assertRaises(OSError):
                self.storage.save("case.md", self.extraction)
        self.assertFalse(self.storage.is_processed("case.md"))
        with self.assertRaises(FileNotFoundError):
            self.storage.read_result("case.md", ".ev.json")
        self.storage.discard_result("case.md")
        self.storage.save("case.md", self.extraction)
        self.assertTrue(self.storage.is_processed("case.md"))

    def test_invalid_upload_does_not_save_other_documents_in_request(self):
        incoming = [
            FileStorage(io.BytesIO(b"valid document"), "valid.md"),
            FileStorage(io.BytesIO(b"\xff"), "invalid.md"),
        ]
        with self.assertRaises(ValueError):
            self.storage.upload(incoming)
        self.assertEqual(self.storage.list(), [])

    def test_oversized_archive_does_not_save_other_documents_in_request(self):
        self.upload("existing.md")
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as target:
            target.writestr("inside.md", "document")
        data = archive.getvalue()
        incoming = [
            FileStorage(io.BytesIO(b"valid document"), "valid.md"),
            FileStorage(io.BytesIO(data), "docs.zip"),
        ]
        with patch("epicrises.documents.upload_reader.MAX_BATCH_BYTES", len(data) - 1):
            with self.assertRaisesRegex(ValueError, "Архив превышает"):
                self.storage.upload(incoming)
        self.assertEqual(self.storage.list(), [{"name": "existing.md", "processed": False}])

    def test_failed_upload_write_rolls_back_only_new_documents(self):
        self.upload("existing.md")
        original = Path.write_bytes

        def fail_second(path, content):
            if path.name == "second.md":
                raise OSError("disk full")
            return original(path, content)

        with patch.object(Path, "write_bytes", fail_second):
            with self.assertRaises(OSError):
                self.upload("first.md", "second.md")
        self.assertEqual(self.storage.list(), [{"name": "existing.md", "processed": False}])


if __name__ == "__main__":
    unittest.main()
