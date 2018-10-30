""" Namespace to keep all application storage keys

Unique keys to identify stored data
Naming convention accounts for the storage scope: application, request, response, configuration and/or resources
All keys are constants with a unique name convention:

    $(SCOPE)_$(NAME)_KEY

 See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""

# REQUIREMENTS:
# - guarantees all keys are unique
# TODO: facilitate key generation
# TODO: hierarchical classification
# TODO: should be read-only (frozen?)


# APP=application
APP_CONFIG_KEY         = __name__ + '.config'
APP_OPENAPI_SPECS_KEY  = __name__ + '.openapi_specs'
APP_SESSION_SECRET_KEY = __name__ + '.session_secret'

APP_DB_ENGINE_KEY      = __name__ + '.db_engine'
APP_DB_SESSION_KEY     = __name__ + '.db_session'
APP_DB_POOL_KEY        = __name__ + '.db_pool'

# RSP=response


# TODO: tool to convert dotted __name__ to section in dict
