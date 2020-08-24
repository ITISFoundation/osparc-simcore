""" db subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T

from simcore_sdk.config.db import CONFIG_SCHEMA as _PG_SCHEMA

CONFIG_SECTION_NAME = "db"


# FIXME: database user password host port minsize maxsize
# CONFIG_SCHEMA = T.Dict({
#    "database": T.String(),
#    "user": T.String(),
#    "password": T.String(),
#    "host": T.Or( T.String, T.Null),
#    "port": T.Or( T.ToInt, T.Null),
#    T.Key("minsize", default=1 ,optional=True): T.ToInt(),
#    T.Key("maxsize", default=4, optional=True): T.ToInt(),
# })


schema = T.Dict(
    {
        T.Key("postgres"): _PG_SCHEMA,
        T.Key("enabled", default=True, optional=True): T.Bool(),
    }
)
