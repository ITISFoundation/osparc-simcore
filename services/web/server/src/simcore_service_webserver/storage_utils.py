import logging
from typing import Tuple

from aiohttp import ClientSession, web
from servicelib.aiohttp.client_session import get_client_session
from yarl import URL

from .constants import APP_SETTINGS_KEY
from .storage_settings import StorageSettings

log = logging.getLogger(__name__)


def get_storage_client_pair(app: web.Application) -> Tuple[ClientSession, URL]:

    # storage service API endpoint
    settings: StorageSettings = app[APP_SETTINGS_KEY].WEBSERVER_STORAGE
    endpoint = settings.base_url

    # an aiohttp-client session to query storage API
    session = get_client_session(app)
    return session, endpoint
