from .documents import documents_api
from .downloads import downloads_api
from .processing import processing_api


def register_routes(app):
    for blueprint in (documents_api, downloads_api, processing_api):
        app.register_blueprint(blueprint)
