from celery import Celery  # type: ignore[import-untyped]
from servicelib.celery.app_server import BaseAppServer

_APP_SERVER_KEY = "app_server"


def get_app_server(app: Celery) -> BaseAppServer:
    app_server = app.conf[_APP_SERVER_KEY]
    assert isinstance(app_server, BaseAppServer)
    return app_server


def set_app_server(app: Celery, app_server: BaseAppServer) -> None:
    app.conf[_APP_SERVER_KEY] = app_server
