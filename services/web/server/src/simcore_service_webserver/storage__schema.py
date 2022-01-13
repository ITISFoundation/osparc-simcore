""" storage subsystem's configuration

    - config-file schema
    - settings
"""

import trafaret as T

CONFIG_SECTION_NAME = "storage"

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key("host", default="storage"): T.String(),
        T.Key("port", default=11111): T.ToInt(),
        T.Key("version", default="v0"): T.Regexp(
            regexp=r"^v\d+"
        ),  # storage API version basepath
    }
)
