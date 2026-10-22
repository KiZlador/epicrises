"""Application composition: configuration, dependencies and HTTP endpoints."""

import os
from pathlib import Path

from flask import Flask, url_for

from epicrises.documents import MAX_BATCH_BYTES
from epicrises.exporting import ExportService
from epicrises.processing import DocumentProcessor, JobQueue
from epicrises.shared.settings import ROOT, Settings, resolve_path

from .http_errors import register_http_handlers
from .routes import api
from .session_cookie import signing_key


def create_app(settings: Settings | None = None, *, processor=None, data_dir: Path | None = None):
    app = Flask(
        __name__,
        template_folder=str(ROOT / "frontend/templates"),
        static_folder=str(ROOT / "frontend/static"),
        static_url_path="/static",
    )
    root = data_dir if data_dir is not None else resolve_path(os.getenv("DATA_DIR", "runtime"))
    root.mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=signing_key(root),
        DATA_DIR=root,
        MAX_CONTENT_LENGTH=MAX_BATCH_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    app.extensions["jobs"] = JobQueue(
        processor if processor is not None else DocumentProcessor(settings or Settings.from_env())
    )
    app.extensions["exports"] = ExportService()
    app.json.sort_keys = False

    @app.context_processor
    def template_helpers():
        return {"static_url": lambda name: url_for("static", filename=name)}

    register_http_handlers(app)
    app.register_blueprint(api)
    return app
