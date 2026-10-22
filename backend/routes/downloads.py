import io

from flask import Blueprint, request, send_file

from backend.http import documents

downloads_api = Blueprint("downloads", __name__)


@downloads_api.get("/download")
def download():
    result = documents().download(
        request.args.get("scope", "all"),
        request.args.get("format", "json"),
        request.args.get("name", ""),
    )
    return send_file(
        io.BytesIO(result.content),
        mimetype=result.mime_type,
        as_attachment=True,
        download_name=result.filename,
    )
