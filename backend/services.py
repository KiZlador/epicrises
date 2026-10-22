"""Application operations shared by the HTTP endpoints."""

from contextlib import contextmanager
from dataclasses import dataclass

from extraction.evidence import browser_citations

from .exports import XLSX_MIME, build_json, build_xlsx, build_zip
from .jobs import Jobs
from .storage import Storage


class ProcessingConflict(Exception):
    pass


@dataclass(frozen=True)
class Download:
    content: bytes
    mime_type: str
    filename: str


class DocumentService:
    def __init__(self, session_id: str, storage: Storage, jobs: Jobs):
        self.session_id = session_id
        self.storage = storage
        self.jobs = jobs

    @contextmanager
    def _mutation(self):
        with self.jobs.lock:
            if self.jobs.busy(self.session_id):
                raise ProcessingConflict("Дождитесь завершения обработки")
            yield

    def list(self):
        with self.jobs.lock:
            return self.storage.list()

    def upload(self, incoming):
        with self._mutation():
            if not incoming:
                raise ValueError("Файлы не переданы")
            result = self.storage.upload(incoming)
            if result["accepted"]:
                self.jobs.reset(self.session_id)
            return result

    def delete(self, name: str | None = None):
        with self._mutation():
            names = [name] if name is not None else [item["name"] for item in self.storage.list()]
            for item in names:
                self.storage.delete(item)
            self.jobs.reset(self.session_id)
            return self.storage.list()

    def start(self):
        return self.jobs.start(self.session_id, self.storage)

    def status(self):
        return self.jobs.status(self.session_id)

    def result(self, name: str, suffix=".json"):
        with self.jobs.lock:
            return self.storage.read_result(name, suffix)

    def source(self, name: str):
        with self.jobs.lock:
            raw = self.storage.raw(name)
            evidence = (
                self.storage.read_result(name, ".ev.json")
                if self.storage.is_processed(name)
                else {}
            )
            return {"text": raw, "citations": browser_citations(raw, evidence)}

    def download(self, scope: str, fmt: str, name: str = "") -> Download:
        if scope not in {"one", "all"} or fmt not in {"json", "xlsx"}:
            raise ValueError("Неизвестный формат экспорта")
        with self.jobs.lock:
            names = (
                [name]
                if scope == "one"
                else [item["name"] for item in self.storage.list() if item["processed"]]
            )
            if not names:
                raise ValueError("Нет обработанных документов")
            results = {item: self.storage.read_result(item) for item in names}
        if fmt == "xlsx":
            return Download(build_xlsx(results), XLSX_MIME, "results.xlsx")
        if scope == "one":
            return Download(build_json(results[name]), "application/json", "result.json")
        return Download(build_zip(results), "application/zip", "results.zip")
