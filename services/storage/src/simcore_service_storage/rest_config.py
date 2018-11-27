""" rest subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T

from .settings import APP_OPENAPI_SPECS_KEY

APP_OPENAPI_SPECS_KEY = APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = 'rest'

schema = T.Dict({
    T.Key("oas_repo"): T.Or(T.String, T.URL),   # either path or url should contain version in it
})
