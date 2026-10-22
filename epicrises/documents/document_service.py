"""Upload, read and delete documents within a session."""

from contextlib import contextmanager

from .coordination import ProcessingConflict, SessionCoordinator
from .document_store import DocumentStore


class DocumentService:
    def __init__(self, session_id: str, storage: DocumentStore, coordinator: SessionCoordinator):
        self.session_id = session_id
        self.storage = storage
        self.coordinator = coordinator

    @contextmanager
    def _mutation(self):
        with self.coordinator.lock:
            if self.coordinator.busy(self.session_id):
                raise ProcessingConflict("Дождитесь завершения обработки")
            yield

    def list(self):
        with self.coordinator.lock:
            return self.storage.list()

    def upload(self, incoming):
        with self._mutation():
            if not incoming:
                raise ValueError("Файлы не переданы")
            result = self.storage.upload(incoming)
            if result["accepted"]:
                self.coordinator.reset(self.session_id)
            return result

    def delete(self, name: str | None = None):
        with self._mutation():
            names = [name] if name is not None else [item["name"] for item in self.storage.list()]
            for item in names:
                self.storage.delete(item)
            self.coordinator.reset(self.session_id)
            return self.storage.list()

    def result(self, name: str, suffix=".json"):
        with self.coordinator.lock:
            return self.storage.read_result(name, suffix)

    def source(self, name: str):
        with self.coordinator.lock:
            raw = self.storage.raw(name)
            evidence = (
                self.storage.read_result(name, ".ev.json")
                if self.storage.is_processed(name)
                else {}
            )
            return {"text": raw, "evidence": evidence}

    def results_snapshot(self, scope: str, name: str = "") -> dict:
        if scope not in {"one", "all"}:
            raise ValueError("Неизвестная область экспорта")
        with self.coordinator.lock:
            names = (
                [name]
                if scope == "one"
                else [item["name"] for item in self.storage.list() if item["processed"]]
            )
            if not names:
                raise ValueError("Нет обработанных документов")
            return {item: self.storage.read_result(item) for item in names}
