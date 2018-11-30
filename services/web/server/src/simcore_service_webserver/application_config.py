""" app's configuration

    This module loads the schema defined by every subsystem and injects it in the
    application's configuration scheams

    It was designed in a similar fashion to the setup protocol of the application
    where every subsystem is imported and queried in a specific order. The application
    depends on the subsystem and not the other way around.

    The app configuration is created before the application instance exists.


TODO: add more strict checks with re
TODO: add support for versioning.
    - check shema fits version
    - parse/format version in schema
TODO: add simcore_sdk.config.s3 section!!!
"""
import logging

import trafaret as T

from servicelib import application_keys  # pylint:disable=unused-import

from . import (computation_config, db_config, email_config, rest_config,
               storage_config)
from .director import config as director_config
from .resources import resources
from .login import config as login_config

log = logging.getLogger(__name__)


def create_schema():
    """
        Build schema for the configuration's file
        by aggregating all the subsystem configurations
    """
    schema = T.Dict({
        "version": T.String(),
        "main": T.Dict({
            "host": T.IP,
            "port": T.Int(),
            "client_outdir": T.String(),
            "log_level": T.Enum(*logging._nameToLevel.keys()), # pylint: disable=protected-access
            "testing": T.Bool(),
        }),
        db_config.CONFIG_SECTION_NAME: db_config.schema,
        director_config.CONFIG_SECTION_NAME: director_config.schema,
        rest_config.CONFIG_SECTION_NAME: rest_config.schema,
        email_config.CONFIG_SECTION_NAME: email_config.schema,
        computation_config.CONFIG_SECTION_NAME: computation_config.schema,
        storage_config.CONFIG_SECTION_NAME: storage_config.schema,
        T.Key(login_config.CONFIG_SECTION_NAME, optional=True): login_config.schema
        #s3_config.CONFIG_SECTION_NAME: s3_config.schema
        #TODO: enable when sockets are refactored
    })


    section_names = [k.name for k in schema.keys]
    assert len(section_names) == len(set(section_names)), "Found repeated section names in %s" % section_names

    return schema


CLI_DEFAULT_CONFIGFILE = 'server-defaults.yaml'
app_schema = create_schema() # TODO: rename as schema

assert resources.exists( 'config/' + CLI_DEFAULT_CONFIGFILE )
