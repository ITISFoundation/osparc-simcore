#pylint: disable=C0111
import simcore_director_sdk
from aiohttp import web
from simcore_director_sdk import UsersApi
from simcore_director_sdk import ApiException  # pylint: disable=W0611
from yarl import URL

from .config import get_config


def create_director_api_client(app: web.Application):
    cfg = get_config(app)
    # TODO: redundant with director_api._get_director_client!
    endpoint = URL.build(scheme='http',
                         host=cfg['host'],
                         port=cfg['port']).with_path(cfg['version'])

    configuration = simcore_director_sdk.Configuration()
    configuration.host = str(endpoint)
    api_instance = UsersApi(simcore_director_sdk.ApiClient(configuration))
    return api_instance
