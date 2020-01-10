import trafaret as T

from servicelib.tracing import schema as tracing_schema
from simcore_sdk.config import db, s3

from . import rest_config

app_schema = T.Dict({
    T.Key("host", default="0.0.0.0"): T.IP,
    "port": T.Int(),
    "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"),
    "testing": T.Bool(),
    T.Key("max_workers", default=8, optional=True) : T.Int(),
    T.Key("monitoring_enabled", default=False): T.Or(T.Bool(), T.Int), # Int added to use environs
    T.Key("test_datcore", optional=True): T.Dict({
        "token_key": T.String(),
        "token_secret": T.String()
    }),
    T.Key("disable_services", default=[], optional=True): T.List(T.String())
})

schema = T.Dict({
    "version": T.String(),
    T.Key("main"): app_schema,
    T.Key("postgres"): db.CONFIG_SCHEMA,
    T.Key("s3"): s3.CONFIG_SCHEMA,
    T.Key(rest_config.CONFIG_SECTION_NAME): rest_config.schema,
    T.Key("tracing"): tracing_schema
})


# TODO: config submodule that knows about schema with web.Application intpu parameters
# TODO: def get_main_config(app: ):
