""" Namespace to keep all application storage keys

Unique keys to identify stored data
Naming convention accounts for the storage scope: application, request, response, configuration and/or resources
All keys are constants with a unique name convention:

    $(SCOPE)_$(NAME)_KEY

 See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""

# REQUIREMENTS:
# - guarantees all keys are unique
# - one place for all common keys
# - hierarchical classification
# TODO: should be read-only (frozen?)

#
# web.Application keys, i.e. app[APP_*_KEY]
#
APP_CONFIG_KEY           = f'{__name__ }.config'
APP_OPENAPI_SPECS_KEY    = f'{__name__ }.openapi_specs'
APP_JSONSCHEMA_SPECS_KEY = f'{__name__ }.jsonschema_specs'

APP_DB_ENGINE_KEY        = f'{__name__ }.db_engine'

APP_CLIENT_SESSION_KEY   = f'{__name__ }.session'

#
# web.Response keys, i.e. app[RSP_*_KEY]
#
