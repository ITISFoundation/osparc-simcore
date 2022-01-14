""" rest subsystem's configuration

    - config-file schema
    - settings
"""

import trafaret as T

CONFIG_SECTION_NAME = "rest"

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        "version": T.Enum("v0"),
    }
)
