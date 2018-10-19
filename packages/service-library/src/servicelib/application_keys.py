""" Namespace to keep all application storage keys

Unique keys to identify stored data
Naming convention accounts for the storage scope: application, request, response, configuration and/or resources
All keys are constants with a unique name convention:

    $(SCOPE)_$(NAME)_KEY

 See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""

_PREFIX = "simcore.app."

# APP=application
APP_CONFIG_KEY         = _PREFIX + 'config'
APP_OPENAPI_SPECS_KEY  = _PREFIX + 'openapi_specs'
APP_SESSION_SECRET_KEY = _PREFIX + 'session_secret'

APP_DB_ENGINE_KEY      = _PREFIX + 'db_engine'
APP_DB_SESSION_KEY     = _PREFIX + 'db_session'


# TODO:
# TODO: freeze contants so they are not rewritable?
# RQT=request

# RSP=response

# TODO: gurantee all keys are unique
# TODO: facilitate key generation
# TODO: can be classified easily
