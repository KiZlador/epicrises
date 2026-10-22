from flask import Blueprint, jsonify

from backend.http import documents

processing_api = Blueprint("processing", __name__)


@processing_api.post("/process")
def process():
    try:
        state = documents().start()
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(state), 200 if state["total"] == 0 else 202


@processing_api.get("/process/status")
def process_status():
    return jsonify(documents().status())
