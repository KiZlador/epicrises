"""Session-scoped documents and committed extraction results."""

import json
from pathlib import Path

from domain.files import read_document, write_json
from domain.validation import validate_result

from .uploads import read_uploads

ARTIFACTS = {".json": "result.json", ".ev.json": "evidence.json", ".report.json": "report.json"}


class Storage:
    def __init__(self, root: Path):
        self.root = root
        self.uploads = root / "uploads"
        self.results = root / "results"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)

    def document(self, name: str) -> Path:
        if (
            not name
            or name != Path(name).name
            or "/" in name
            or "\\" in name
            or not name.lower().endswith(".md")
        ):
            raise ValueError("Недопустимое имя документа")
        return self.uploads / name

    def result_path(self, name: str, suffix=".json") -> Path:
        return self.results / self.document(name).name / ARTIFACTS[suffix]

    def _legacy_path(self, name: str, suffix: str) -> Path:
        return self.results / (self.document(name).stem + suffix)

    def _legacy_complete(self, name: str) -> bool:
        """Accept complete old bundles, excluding sidecars that resemble a result."""
        paths = [self._legacy_path(name, suffix) for suffix in ARTIFACTS]
        if not all(path.is_file() for path in paths):
            return False
        try:
            result = json.loads(paths[0].read_text(encoding="utf-8"))
            validate_result(result)
            evidence = json.loads(paths[1].read_text(encoding="utf-8"))
            report = json.loads(paths[2].read_text(encoding="utf-8"))
            if not isinstance(report, dict) or not {
                "mode",
                "seconds",
                "analysis",
                "changes",
                "warnings",
            }.issubset(report):
                return False
            return all(
                evidence[group][key]["value"] == value
                for group, fields in result.items()
                for key, value in fields.items()
            )
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
            return False

    def is_processed(self, name: str) -> bool:
        if self.result_path(name).parent.exists():
            return all(self.result_path(name, suffix).is_file() for suffix in ARTIFACTS)
        return self._legacy_complete(name)

    def list(self):
        return [
            {"name": path.name, "processed": self.is_processed(path.name)}
            for path in sorted(self.uploads.glob("*.md"), key=lambda path: path.name.casefold())
            if path.is_file()
        ]

    def read_result(self, name: str, suffix=".json"):
        if not self.document(name).is_file() or not self.is_processed(name):
            raise FileNotFoundError(name)
        path = self.result_path(name, suffix)
        if not path.is_file():
            path = self._legacy_path(name, suffix)
        return json.loads(path.read_text(encoding="utf-8"))

    def raw(self, name: str):
        return read_document(self.document(name))

    def discard_result(self, name: str):
        # Old flat filenames can be shared by two document names. Keep shared
        # paths until the other document is deleted, even for incomplete bundles.
        protected = {
            self._legacy_path(path.name, suffix)
            for path in self.uploads.glob("*.md")
            if path.is_file() and path.name != name
            for suffix in ARTIFACTS
        }
        for suffix in ARTIFACTS:
            path = self._legacy_path(name, suffix)
            if path not in protected:
                path.unlink(missing_ok=True)
        for suffix in ARTIFACTS:
            self.result_path(name, suffix).unlink(missing_ok=True)
        directory = self.result_path(name).parent
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()

    def save(self, name: str, extraction):
        # The main result commits the bundle only after both sidecars have been written.
        write_json(self.result_path(name, ".ev.json"), extraction.evidence or {})
        write_json(self.result_path(name, ".report.json"), extraction.report)
        write_json(self.result_path(name), extraction.result)

    def delete(self, name: str):
        self.discard_result(name)
        self.document(name).unlink(missing_ok=True)
        (self.root / "batch-report.json").unlink(missing_ok=True)

    def upload(self, incoming):
        batch = read_uploads(incoming, [item["name"] for item in self.list()])
        accepted = []
        try:
            for document in batch.documents:
                path = self.document(document.name)
                accepted.append(document.name)
                path.write_bytes(document.text.encode("utf-8"))
        except OSError:
            for name in accepted:
                self.document(name).unlink(missing_ok=True)
            raise
        if accepted:
            (self.root / "batch-report.json").unlink(missing_ok=True)
        return {"accepted": accepted, "skipped": batch.skipped}
