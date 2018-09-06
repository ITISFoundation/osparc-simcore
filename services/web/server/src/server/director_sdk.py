import os
import logging
import simcore_director_sdk

_LOGGER = logging.getLogger(__file__)

_DIRECTOR_HOST = os.environ.get("DIRECTOR_HOST", "0.0.0.0")
_DIRECTOR_PORT = os.environ.get("DIRECTOR_PORT", "8001")
_DIRECTOR_PATH = "v1"


def get_director():
    _LOGGER.debug("HOST is %s", _DIRECTOR_HOST)
    configuration = simcore_director_sdk.Configuration()
    configuration.host = configuration.host.format(host=_DIRECTOR_HOST, port=_DIRECTOR_PORT, version=_DIRECTOR_PATH)
    api_instance = simcore_director_sdk.UsersApi(simcore_director_sdk.ApiClient(configuration))
    return api_instance