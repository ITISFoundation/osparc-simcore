import os
import logging
import simcore_director_sdk

from .config import get_config
from yarl import URL
from aiohttp import web

logger = logging.getLogger(__file__)

# TODO: deprecate!!!
_DIRECTOR_HOST = os.environ.get("DIRECTOR_HOST", "0.0.0.0")
_DIRECTOR_PORT = os.environ.get("DIRECTOR_PORT", "8001")
_DIRECTOR_PATH = "v0"


def get_director():
    # TODO: deprecate, use instead create_client!!!
    configuration = simcore_director_sdk.Configuration()
    configuration.host = "http://{}:{}/{}".format(
            _DIRECTOR_HOST,
            _DIRECTOR_PORT,
            _DIRECTOR_PATH)
    api_instance = simcore_director_sdk.UsersApi(
        simcore_director_sdk.ApiClient(configuration))
    return api_instance


def create_client(app: web.Application):
    cfg = get_config(app)
    endpoint = URL.build(scheme='http',
                         host=cfg['host'],
                         port=cfg['port']).with_path(cfg['version'])

    configuration = simcore_director_sdk.Configuration()
    configuration.host = str(endpoint)
    api_instance = simcore_director_sdk.UsersApi(
        simcore_director_sdk.ApiClient(configuration))
    return api_instance
