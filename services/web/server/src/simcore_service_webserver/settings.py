""" Configuration

TODO: add more strict checks with re
"""
import logging

import trafaret as T

from servicelib import application_keys  # pylint:disable=unused-import
from simcore_sdk.config import db, rabbit, s3

from .director_config import DIRECTOR_SERVICE, director_schema

log = logging.getLogger(__name__)


def create_configfile_schema():
    # should have per module?
    _DB_SCHEMA = T.Dict({
        T.Key("init_tables", default=False): T.Bool()
    })

    # TODO: app schema should be organizeds as __name__ modules
    #   or perhaps every module should inject its own settings (like in a plugin manners)
    _APP_SCHEMA = T.Dict({
        "host": T.IP,
        "port": T.Int(),
        T.Key("public_url", optional=True): T.Or(T.String(), T.List(T.String)),  # full url seen by front-end
        "client_outdir": T.String(),
        "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL", "NOTSET"), # TODO: auto-add all logging levels
        "testing": T.Bool(),
        T.Key("disable_services", default=[], optional=True): T.List(T.String()),
        T.Key("db", optional=True): _DB_SCHEMA
    })


    _SMTP_SERVER = T.Dict({
    T.Key('sender', default='OSPARC support <crespo@itis.swiss>'): T.String(), # FIXME: email format
    'host': T.String(),
    'port': T.Int(),
    T.Key('tls', default=False): T.Bool(),
    T.Key('username', default=None): T.Or(T.String, T.Null),
    T.Key('password', default=None): T.Or(T.String, T.Null)
    })

    # TODO: add support for versioning.
    #   - check shema fits version
    #   - parse/format version in schema
    return T.Dict({
        "version": T.String(),
        T.Key("main"): _APP_SCHEMA,
        T.Key("smtp"): _SMTP_SERVER,
        T.Key(DIRECTOR_SERVICE): director_schema,
        T.Key("postgres"): db.CONFIG_SCHEMA,
        T.Key("rabbit"): rabbit.CONFIG_SCHEMA,
        T.Key("s3"): s3.CONFIG_SCHEMA
    })


CONFIG_SCHEMA = create_configfile_schema()

CLI_DEFAULT_CONFIGFILE = 'server-defaults.yaml' # TODO: test always exists
