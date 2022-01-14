""" catalog's subsystem configuration

    - config-file schema
    - settings
"""
import os

import trafaret as T

CONFIG_SECTION_NAME = "catalog"


_default_values = {
    "host": os.environ.get("CATALOG_HOST", "catalog"),
    "port": int(os.environ.get("CATALOG_PORT", 8000)),
}

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key("host", default=_default_values["host"]): T.String(),
        T.Key("port", default=_default_values["port"]): T.ToInt(),
        T.Key("version", default="v0"): T.Regexp(
            regexp=r"^v\d+"
        ),  # catalog API version basepath
    }
)
