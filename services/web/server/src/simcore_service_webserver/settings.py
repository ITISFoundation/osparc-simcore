""" Configuration

TODO: add more strict checks with re
"""
import logging

import trafaret as T

from simcore_sdk.config import (
    db,
    rabbit,
    s3
)

log = logging.getLogger(__name__)


def create_configfile_schema():
    # TODO: import from director
    _DIRECTOR_SCHEMA = T.Dict({
        "host": T.String(),
        "port": T.Int()
    })

    _APP_SCHEMA = T.Dict({
        "host": T.IP,
        "port": T.Int(),
        "client_outdir": T.String(),
        "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"),
        "testing": T.Bool(),
        T.Key("disable_services", default=[], optional=True): T.List(T.String())
    })

    # TODO: add support for versioning.
    #   - check shema fits version
    #   - parse/format version in schema
    return T.Dict({
        "version": T.String(),
        T.Key("main"): _APP_SCHEMA,
        T.Key("director"): _DIRECTOR_SCHEMA,
        T.Key("postgres"): db.CONFIG_SCHEMA,
        T.Key("rabbit"): rabbit.CONFIG_SCHEMA,
        T.Key("s3"): s3.CONFIG_SCHEMA
    })


CONFIG_SCHEMA = create_configfile_schema()

CLI_DEFAULT_CONFIGFILE = 'server-defaults.yaml' # TODO: test always exists
