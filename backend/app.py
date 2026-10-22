"""Application composition: configuration, dependencies and HTTP endpoints."""

import os
from pathlib import Path

from flask import Flask, url_for

from domain.config import ROOT, Settings, resolve_path
from extraction.pipeline import Pipeline

from .http import register_http_handlers
from .jobs import Jobs
from .routes import register_routes
from .sessions import signing_key
from .uploads import MAX_BATCH_BYTES


def create_app(settings: Settings | None = None, *, pipeline=None, data_dir: Path | None = None):
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
    app.extensions["jobs"] = Jobs(
        pipeline if pipeline is not None else Pipeline(settings or Settings.from_env())
    )
    app.json.sort_keys = False

    @app.context_processor
    def template_helpers():
        return {"static_url": lambda name: url_for("static", filename=name)}

    register_http_handlers(app)
    register_routes(app)
    return app
