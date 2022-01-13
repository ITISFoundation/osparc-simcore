""" director subsystem's configuration

    - config-file schema
    - settings
"""

import trafaret as T

APP_DIRECTOR_API_KEY = __name__ + ".director_api"

CONFIG_SECTION_NAME = "director"

# TODO: deprecate trafaret schema
schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key(
            "host",
            default="director",
        ): T.String(),
        T.Key("port", default=8001): T.ToInt(),
        T.Key("version", default="v0"): T.Regexp(
            regexp=r"^v\d+"
        ),  # director API version basepath
    }
)
