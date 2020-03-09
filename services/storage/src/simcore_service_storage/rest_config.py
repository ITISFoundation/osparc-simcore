""" rest subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T
from servicelib.config_schema_utils import minimal_addon_schema

from .settings import APP_OPENAPI_SPECS_KEY

CONFIG_SECTION_NAME: str = "rest"

schema: T.Dict = minimal_addon_schema()

__all__ = ("APP_OPENAPI_SPECS_KEY", "CONFIG_SECTION_NAME", "schema")
