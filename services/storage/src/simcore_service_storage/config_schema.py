import os

import trafaret as T

from servicelib.config_schema_utils import addon_section
from servicelib.tracing import schema as tracing_schema
from simcore_sdk.config import db, s3

from . import rest_config

in_container = "SC_BUILD_TARGET" in os.environ

app_schema = T.Dict(
    {
        T.Key(
            "host", default="0.0.0.0" if in_container else "127.0.0.1"  # nosec
        ): T.IP,
        "port": T.ToInt(),
        "log_level": T.Enum(
            "DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"
        ),
        "testing": T.Bool(),
        T.Key("max_workers", default=8, optional=True): T.ToInt(),
        T.Key("monitoring_enabled", default=False): T.Or(
            T.Bool(), T.ToInt
        ),  # Int added to use environs
        T.Key("test_datcore", optional=True): T.Dict(
            {"token_key": T.String(), "token_secret": T.String()}
        ),
        T.Key("disable_services", default=[], optional=True): T.List(T.String()),
    }
)


schema = T.Dict(
    {
        "version": T.String(),
        T.Key("main"): app_schema,
        T.Key("postgres"): db.CONFIG_SCHEMA,
        T.Key("s3"): s3.CONFIG_SCHEMA,
        addon_section(
            rest_config.CONFIG_SECTION_NAME, optional=True
        ): rest_config.schema,
        T.Key("tracing"): tracing_schema,
    }
)


# TODO: config submodule that knows about schema with web.Application intpu parameters
# TODO: def get_main_config(app: ):
