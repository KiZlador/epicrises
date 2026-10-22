from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from epicrises.documents import ProcessingConflict


def register_http_handlers(app):
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

    @app.errorhandler(ProcessingConflict)
    def processing_conflict(exc):
        return jsonify(error=str(exc)), 409
