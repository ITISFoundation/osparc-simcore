""" Common service configuration settings

The application can consume settings revealed at different
stages of the development workflow. This submodule gives access
to all of them.

"""
# CONSTANTS--------------------


# STORAGE KEYS -------------------------
#  Keys used in different scopes. Common naming format:
#
#    $(SCOPE)_$(NAME)_KEY
#
# See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please

# APP=application
APP_CONFIG_KEY ='config'
APP_OAS_KEY    ="openapi_specs"

# CFG=configuration


# RSC=resource



# RQT=request


# RSP=response


## Settings revealed at runtime: only known when the application starts
#  - via the config file passed to the cli
