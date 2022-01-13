""" db subsystem's configuration

    - config-file schema
    - settings
"""

import trafaret as T

_PG_SCHEMA = T.Dict(
    {
        "database": T.String(),
        "user": T.String(),
        "password": T.String(),
        T.Key("minsize", default=1, optional=True): T.ToInt(),
        T.Key("maxsize", default=4, optional=True): T.ToInt(),
        "host": T.Or(T.String, T.Null),
        "port": T.Or(T.ToInt, T.Null),
        "endpoint": T.Or(T.String, T.Null),
    }
)

CONFIG_SECTION_NAME = "db"

schema = T.Dict(
    {
        T.Key("postgres"): _PG_SCHEMA,
        T.Key("enabled", default=True, optional=True): T.Bool(),
    }
)
