""" Namespace to keep all application storage keys

Unique keys to identify stored data
Naming convention accounts for the storage scope: application, request, response, configuration and/or resources
All keys are constants with a unique name convention:

    $(SCOPE)_$(NAME)_KEY

 See https://aiohttp.readthedocs.io/en/stable/web_advanced.html#data-sharing-aka-no-singletons-please
"""
import warnings

warnings.warn("Use servicelib.settings.application_keys instead",
    DeprecationWarning)

#pylint: disable=W0401
#pylint: disable=W0614
from .settings.application_keys import *
