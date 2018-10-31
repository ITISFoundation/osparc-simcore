import trafaret as T

from simcore_sdk.config import db, s3

## Config file schema
# FIXME: load from json schema instead!
_APP_SCHEMA = T.Dict({
    T.Key("host", default="0.0.0.0"): T.IP,
    "port": T.Int(),
    "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"),
    "testing": T.Bool(),
    "python2": T.String(),
    T.Key("max_workers", default=8, optional=True) : T.Int(),
    T.Key("test_datcore", optional=True): T.Dict({
        "api_token": T.String(),
        "api_secret": T.String()
    }),
    T.Key("disable_services", default=[], optional=True): T.List(T.String())
})

CONFIG_SCHEMA = T.Dict({
    "version": T.String(),
    T.Key("main"): _APP_SCHEMA,
    T.Key("postgres"): db.CONFIG_SCHEMA,
    T.Key("s3"): s3.CONFIG_SCHEMA
})


# TODO: config submodule that knows about schema with web.Application intpu parameters
# TODO: def get_main_config(app: ):
