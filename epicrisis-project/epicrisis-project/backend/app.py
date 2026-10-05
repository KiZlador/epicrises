import io
import os
import re
import secrets
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_file, session, url_for
from werkzeug.exceptions import HTTPException

from domain.config import ROOT, Settings, resolve_path
from extraction.evidence import browser_citations
from extraction.pipeline import Pipeline

from .exports import XLSX_MIME, build_json, build_xlsx, build_zip
from .jobs import Jobs
from .storage import MAX_BATCH_BYTES, Storage


def create_app(settings=None):
    app = Flask(
        __name__,
        template_folder=str(ROOT / "frontend/templates"),
        static_folder=str(ROOT / "frontend/static"),
        static_url_path="/static",
    )
    data_dir = resolve_path(os.getenv("DATA_DIR", "runtime"))
    data_dir.mkdir(parents=True, exist_ok=True)
    secret = os.getenv("SECRET_KEY")
    if not secret:
        secret_path = data_dir / ".secret"
        try:
            descriptor = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            secret = secret_path.read_text(encoding="ascii")
        else:
            secret = secrets.token_hex(32)
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(secret)
    app.config.update(
        SECRET_KEY=secret,
        MAX_CONTENT_LENGTH=MAX_BATCH_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    jobs = Jobs(Pipeline(settings or Settings.from_env()))
    app.json.sort_keys = False

    @app.context_processor
    def template_helpers():
        return {"static_url": lambda name: url_for("static", filename=name)}

    def storage():
        identifier = session.get("id", "")
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            identifier = uuid4().hex
            session["id"] = identifier
        return identifier, Storage(data_dir / identifier)

    @app.before_request
    def same_origin():
        if request.method in {"POST", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                return jsonify(error="Запрос с другого источника запрещён"), 403

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description), exc.code

    @app.errorhandler(ValueError)
    def bad_input(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(FileNotFoundError)
    def missing_file(exc):
        return jsonify(error="Документ или результат не найден"), 404

    @app.get("/")
    def index():
        storage()
        return render_template("index.html")

    @app.route("/files", methods=["GET", "DELETE"])
    def files():
        identifier, store = storage()
        with jobs.lock:
            if request.method == "DELETE":
                if jobs.busy(identifier):
                    return jsonify(error="Дождитесь завершения обработки"), 409
                for item in store.list():
                    store.delete(item["name"])
                jobs.states.pop(identifier, None)
            return jsonify(files=store.list())

    @app.delete("/files/<name>")
    def delete_file(name):
        identifier, store = storage()
        with jobs.lock:
            if jobs.busy(identifier):
                return jsonify(error="Дождитесь завершения обработки"), 409
            store.delete(name)
            jobs.states.pop(identifier, None)
        return jsonify(ok=True)

    @app.post("/upload")
    def upload():
        identifier, store = storage()
        with jobs.lock:
            if jobs.busy(identifier):
                return jsonify(error="Дождитесь завершения обработки"), 409
            incoming = request.files.getlist("files")
            if not incoming:
                raise ValueError("Файлы не переданы")
            result = store.upload(incoming)
            if result["accepted"]:
                jobs.states.pop(identifier, None)
            return jsonify(result)

    @app.post("/process")
    def process():
        identifier, store = storage()
        try:
            return jsonify(jobs.start(identifier, store)), 202
        except RuntimeError as exc:
            return jsonify(error=str(exc)), 503

    @app.get("/process/status")
    def process_status():
        identifier, _ = storage()
        return jsonify(jobs.status(identifier))

    @app.get("/result/<name>")
    def result(name):
        _, store = storage()
        with jobs.lock:
            return jsonify(store.read_result(name))

    @app.get("/evidence/<name>")
    def evidence(name):
        _, store = storage()
        with jobs.lock:
            return jsonify(store.read_result(name, ".ev.json"))

    @app.get("/report/<name>")
    def report(name):
        _, store = storage()
        with jobs.lock:
            return jsonify(store.read_result(name, ".report.json"))

    @app.get("/source/<name>")
    def source(name):
        _, store = storage()
        with jobs.lock:
            raw = store.raw(name)
            data = store.read_result(name, ".ev.json") if store.result_path(name).exists() else {}
            return jsonify(text=raw, citations=browser_citations(raw, data))

    @app.get("/download")
    def download():
        _, store = storage()
        scope, fmt = request.args.get("scope", "all"), request.args.get("format", "json")
        if scope not in {"one", "all"} or fmt not in {"json", "xlsx"}:
            raise ValueError("Неизвестный формат экспорта")
        with jobs.lock:
            names = (
                [request.args.get("name", "")]
                if scope == "one"
                else [item["name"] for item in store.list() if item["processed"]]
            )
            if not names:
                raise ValueError("Нет обработанных документов")
            results = {name: store.read_result(name) for name in names}
        if fmt == "xlsx":
            payload, mime, filename = build_xlsx(results), XLSX_MIME, "results.xlsx"
        elif scope == "one":
            payload, mime, filename = (
                build_json(results[names[0]]),
                "application/json",
                "result.json",
            )
        else:
            payload, mime, filename = build_zip(results), "application/zip", "results.zip"
        return send_file(
            io.BytesIO(payload), mimetype=mime, as_attachment=True, download_name=filename
        )

    return app
