import trafaret as T
from simcore_sdk.config import db, s3

## Config file schema
# FIXME: load from json schema instead!
_APP_SCHEMA = T.Dict({
    "host": T.IP,
    "port": T.Int(),
    "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"),
    "testing": T.Bool(),
    T.Key("disable_services", default=[], optional=True): T.List(T.String())
})

CONFIG_SCHEMA = T.Dict({
    "version": T.String(),
    T.Key("main"): _APP_SCHEMA,
    T.Key("postgres"): db.CONFIG_SCHEMA,
    T.Key("s3"): s3.CONFIG_SCHEMA
})
