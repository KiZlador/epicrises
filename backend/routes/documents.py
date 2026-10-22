from flask import Blueprint, jsonify, render_template, request

from backend.http import documents

documents_api = Blueprint("documents", __name__)


@documents_api.get("/")
def index():
    documents()
    return render_template("index.html")


@documents_api.route("/files", methods=["GET", "DELETE"])
def files():
    service = documents()
    items = service.delete() if request.method == "DELETE" else service.list()
    return jsonify(files=items)


@documents_api.delete("/files/<name>")
def delete_file(name):
    documents().delete(name)
    return jsonify(ok=True)


@documents_api.post("/upload")
def upload():
    return jsonify(documents().upload(request.files.getlist("files")))


@documents_api.get("/result/<name>")
def result(name):
    return jsonify(documents().result(name))


@documents_api.get("/evidence/<name>")
def evidence(name):
    return jsonify(documents().result(name, ".ev.json"))


@documents_api.get("/report/<name>")
def report(name):
    return jsonify(documents().result(name, ".report.json"))


@documents_api.get("/source/<name>")
def source(name):
    return jsonify(documents().source(name))
