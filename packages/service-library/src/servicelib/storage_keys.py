""" Common storage keys

Unique keys to identify stored data
Naming convention accounts for the storage scope: application, request, response, configuration and/or resources
All keys are constants with a unique name convention:

    $(SCOPE)_$(NAME)_KEY

 See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""

# APP=application
APP_CONFIG_KEY  = 'config'
APP_OPENAPI_SPECS_KEY = 'openapi_specs'

# CFG=configuration


# RSC=resource


# RQT=request


# RSP=response
