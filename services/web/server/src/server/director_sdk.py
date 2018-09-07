import os
import logging
import simcore_director_sdk

_LOGGER = logging.getLogger(__file__)

# FIXME: This has to come from settings.config._DIRECTOR_SCHEMA schema !
# Better wait until server is merged since there were lots of changes
# this should somehow be setup a la aiohttp provided the configuration issue #195
#
# TIPS:
#
#from .settings.config import _DIRECTOR_SCHEMA
#
# def get_director(config: dict) -> simcore_director_sdk.UserApi:
#    _DIRECTOR_SCHEMA.check(config) # this should be optional since it was already validated?

# def get_director(app) -> simcore_director_sdk.UserApi:
#   if app['services']['director']:
#     ...
#
# OR
#
# def get_director(config: dict) -> simcore_director_sdk.UserApi:
#    _DIRECTOR_SCHEMA.check(config) # this should be optional since it was already validated?
#   ...
#    version needs to be given by simcore_director_sdk!!!
#
#
# notice that app['config']['service']['director'] returns this config
#
# OR cache per session?
#

_DIRECTOR_HOST = os.environ.get("DIRECTOR_HOST", "0.0.0.0")
_DIRECTOR_PORT = os.environ.get("DIRECTOR_PORT", "8001")
_DIRECTOR_PATH = "v1"

def get_director():
    configuration = simcore_director_sdk.Configuration()
    configuration.host = configuration.host.format(host=_DIRECTOR_HOST, port=_DIRECTOR_PORT, version=_DIRECTOR_PATH)
    api_instance = simcore_director_sdk.UsersApi(simcore_director_sdk.ApiClient(configuration))
    return api_instance
