import io

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from .citation_view import browser_citations
from .request_scope import services

api = Blueprint("epicrises", __name__)


@api.get("/")
def index():
    services()
    return render_template("index.html")


@api.route("/files", methods=["GET", "DELETE"])
def files():
    documents = services().documents
    items = documents.delete() if request.method == "DELETE" else documents.list()
    return jsonify(files=items)


@api.delete("/files/<name>")
def delete_file(name):
    services().documents.delete(name)
    return jsonify(ok=True)


@api.post("/upload")
def upload():
    return jsonify(services().documents.upload(request.files.getlist("files")))


@api.get("/result/<name>")
def result(name):
    return jsonify(services().documents.result(name))


@api.get("/evidence/<name>")
def evidence(name):
    return jsonify(services().documents.result(name, ".ev.json"))


@api.get("/report/<name>")
def report(name):
    return jsonify(services().documents.result(name, ".report.json"))


@api.get("/source/<name>")
def source(name):
    data = services().documents.source(name)
    return jsonify(text=data["text"], citations=browser_citations(data["text"], data["evidence"]))


@api.post("/process")
def process():
    context = services()
    try:
        state = context.jobs.start(context.identifier, context.store)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(state), 200 if state["total"] == 0 else 202


@api.get("/process/status")
def process_status():
    context = services()
    return jsonify(context.jobs.status(context.identifier))


@api.get("/download")
def download():
    scope = request.args.get("scope", "all")
    snapshot = services().documents.results_snapshot(scope, request.args.get("name", ""))
    result = current_app.extensions["exports"].download(
        snapshot, request.args.get("format", "json"), single=scope == "one"
    )
    return send_file(
        io.BytesIO(result.content),
        mimetype=result.mime_type,
        as_attachment=True,
        download_name=result.filename,
    )
