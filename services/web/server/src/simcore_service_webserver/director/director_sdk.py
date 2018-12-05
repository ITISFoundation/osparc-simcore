#pylint: disable=C0111
from aiohttp import web
from yarl import URL

import simcore_director_sdk
from simcore_director_sdk import UsersApi
from simcore_director_sdk.rest import ApiException  # pylint: disable=W0611

from .config import get_config


def create_director_api_client(app: web.Application):
    cfg = get_config(app)
    endpoint = URL.build(scheme='http',
                         host=cfg['host'],
                         port=cfg['port']).with_path(cfg['version'])

    configuration = simcore_director_sdk.Configuration()
    configuration.host = str(endpoint)
    api_instance = UsersApi(simcore_director_sdk.ApiClient(configuration))
    return api_instance
