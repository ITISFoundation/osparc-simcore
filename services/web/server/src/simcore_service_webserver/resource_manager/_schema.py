""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""

import trafaret as T

CONFIG_SECTION_NAME = "resource_manager"


schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.ToInt()),
        T.Key(
            "resource_deletion_timeout_seconds", default=900, optional=True
        ): T.ToInt(),
        T.Key(
            "garbage_collection_interval_seconds", default=30, optional=True
        ): T.ToInt(),
        T.Key("redis", optional=False): T.Dict(
            {
                T.Key("enabled", default=True, optional=True): T.Bool(),
                T.Key("host", default="redis", optional=True): T.String(),
                T.Key("port", default=6793, optional=True): T.ToInt(),
            }
        ),
    }
)
