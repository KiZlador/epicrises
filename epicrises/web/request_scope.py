"""Bind application services to the current browser session."""

from dataclasses import dataclass
from pathlib import Path

from flask import current_app, g

from epicrises.documents import DocumentService, DocumentStore
from epicrises.processing import JobQueue

from .session_cookie import session_id


@dataclass(frozen=True)
class SessionServices:
    identifier: str
    store: DocumentStore
    documents: DocumentService
    jobs: JobQueue


def services() -> SessionServices:
    if "services" not in g:
        identifier = session_id()
        store = DocumentStore(Path(current_app.config["DATA_DIR"]) / identifier)
        jobs = current_app.extensions["jobs"]
        g.services = SessionServices(
            identifier, store, DocumentService(identifier, store, jobs), jobs
        )
    return g.services
