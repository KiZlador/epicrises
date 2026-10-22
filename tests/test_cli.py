import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import add_citations
import pipeline
from cli.citations import add_evidence
from domain.config import Settings
from extraction.pipeline import Pipeline

DOC = "Поступил 01.01.2024. Сахарный диабет отрицает. АД 120/80 мм рт. ст."


class CitationCliContracts(unittest.TestCase):
    def test_citations_do_not_rewrite_results_and_continue_after_invalid_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid, invalid = root / "valid.md", root / "invalid.md"
            for path in (valid, invalid):
                path.write_text(DOC, encoding="utf-8")
            result = Pipeline(Settings(llm_enabled=False)).process(DOC).result
            original = json.dumps(result, ensure_ascii=False)
            (root / "valid.json").write_text(original, encoding="utf-8")
            (root / "invalid.json").write_text("{}", encoding="utf-8")
            (root / "invalid.ev.json").write_text("{}", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(add_evidence([invalid, valid], root, None), 1)
            self.assertEqual((root / "valid.json").read_text(encoding="utf-8"), original)
            self.assertFalse((root / "invalid.ev.json").exists())
            evidence = json.loads((root / "valid.ev.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["диагноз"]["dm"]["value"], "0")
            self.assertTrue(evidence["даты эпизода"]["admission_date"]["verified"])

    def test_invalid_environment_is_a_cli_error_in_both_entry_points(self):
        for entry_point in (pipeline, add_citations):
            with (
                self.subTest(command=entry_point.__name__),
                patch.object(sys, "argv", [entry_point.__name__, "--regex-only"]),
                patch.dict(os.environ, {"MODEL_CONTEXT": "not-a-number"}),
                redirect_stderr(io.StringIO()) as errors,
                self.assertRaises(SystemExit) as raised,
            ):
                entry_point.main()
            self.assertEqual(raised.exception.code, 2)
            self.assertNotIn("Traceback", errors.getvalue())


class ExtractionCliContracts(unittest.TestCase):
    def test_injected_pipeline_only_needs_processing_interface(self):
        extraction = Pipeline(Settings(llm_enabled=False)).process(DOC)
        processor = SimpleNamespace(prepare=Mock(), process=Mock(return_value=extraction))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = root / "documents"
            documents.mkdir()
            (documents / "case.md").write_text(DOC, encoding="utf-8")
            metrics = root / "metrics.json"
            args = [
                "pipeline.py",
                "--regex-only",
                "--input",
                str(documents),
                "--output",
                str(root / "results"),
                "--metrics",
                str(metrics),
            ]
            with (
                patch.object(sys, "argv", args),
                patch.object(pipeline, "Pipeline", return_value=processor),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(pipeline.main(), 0)
            processor.process.assert_called_once_with(DOC)
            report = json.loads(metrics.read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "regex-statistics")
            self.assertFalse(report["includes_model_loading"])


if __name__ == "__main__":
    unittest.main()
