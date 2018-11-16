""" rest subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T

from servicelib.application_keys import APP_OPENAPI_SPECS_KEY

APP_OPENAPI_SPECS_KEY = APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = 'rest'

schema = T.Dict({
    "version": T.Enum("v0"),
    "location": T.Or(T.String, T.URL),   # either path or url should contain version in it
    T.Key("extra_urls", optional=True): T.Or(T.String(), T.List(T.String)),  # full url seen by front-end
})
