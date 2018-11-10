""" app's configuration


TODO: add more strict checks with re
TODO: add support for versioning.
    - check shema fits version
    - parse/format version in schema
TODO  add simcore_sdk.config.s3 section!!!
TODO: create decorator so every module injects sections in a global schema. This way we avoid cyclic dependencies
"""
import logging

import trafaret as T

from servicelib import application_keys  # pylint:disable=unused-import

from . import (computation_config, db_config, director_config, email_config,
               rest_config)
from .resources import resources

log = logging.getLogger(__name__)


def create_schema():
    """
        Build schema for the configuration's file

    """
    schema = T.Dict({
        "version": T.String(),
        "main": T.Dict({
            "host": T.IP,
            "port": T.Int(),
            T.Key("public_url", optional=True): T.Or(T.String(), T.List(T.String)),  # full url seen by front-end
            "client_outdir": T.String(),
            "log_level": T.Enum( list(logging._nameToLevel.keys()) ), # pylint: disable=W0212
            "testing": T.Bool(),
            T.Key("disable_services", default=[], optional=True): T.List(T.String()), # TODO: optional enable function in every section
        }),
        db_config.CONFIG_SECTION_NAME: db_config.schema,
        director_config.CONFIG_SECTION_NAME: director_config.schema,
        rest_config.CONFIG_SECTION_NAME: rest_config.schema,
        email_config.CONFIG_SECTION_NAME: email_config.schema,
        computation_config.CONFIG_SECTION_NAME: computation_config.schema,
    })


    section_names = [k.name for k in schema.keys]
    assert len(section_names) == set(section_names), "Found repeated section names in %s" % section_names

    return schema


CLI_DEFAULT_CONFIGFILE = 'server-defaults.yaml'
CONFIG_SCHEMA = create_schema()

assert resources.exists( 'config/' + CLI_DEFAULT_CONFIGFILE )
