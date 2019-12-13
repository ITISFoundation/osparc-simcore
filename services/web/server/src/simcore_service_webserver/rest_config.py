""" rest subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T
from servicelib.application_keys import APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME = 'rest'

schema = T.Dict({
    "version": T.Enum("v0"),
})

__all__ =[
    'APP_OPENAPI_SPECS_KEY'
]
