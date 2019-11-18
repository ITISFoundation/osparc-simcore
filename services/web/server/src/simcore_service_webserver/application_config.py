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
               session_config, storage_config)
from .director import config as director_config
from .activity import config as activity_config
from .login import config as login_config
from .projects import config as projects_config
from .socketio import config as socketio_config
from .resource_manager import config as resource_manager_config
from .resources import resources
from . import tracing


log = logging.getLogger(__name__)


def addon_section(name: str, optional: bool=False) -> T.Key:
    if optional:
        return T.Key(name, default=dict(enabled=True), optional=optional)
    return T.Key(name)

def minimal_addon_schema() -> T.Dict:
    return T.Dict({
            T.Key("enabled", default=True, optional=True): T.Bool()
        })


def create_schema() -> T.Dict:
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
            T.Key("studies_access_enabled", default=False): T.Or(T.Bool(), T.Int),

            T.Key("monitoring_enabled", default=False): T.Or(T.Bool(), T.Int), # Int added to use environs
        }),
        addon_section(tracing.tracing_section_name, optional=True): tracing.schema,
        db_config.CONFIG_SECTION_NAME: db_config.schema,
        director_config.CONFIG_SECTION_NAME: director_config.schema,
        rest_config.CONFIG_SECTION_NAME: rest_config.schema,
        projects_config.CONFIG_SECTION_NAME: projects_config.schema,
        email_config.CONFIG_SECTION_NAME: email_config.schema,
        computation_config.CONFIG_SECTION_NAME: computation_config.schema,
        storage_config.CONFIG_SECTION_NAME: storage_config.schema,
        addon_section(login_config.CONFIG_SECTION_NAME, optional=True): login_config.schema,
        addon_section(socketio_config.CONFIG_SECTION_NAME, optional=True): socketio_config.schema,
        session_config.CONFIG_SECTION_NAME: session_config.schema,
        activity_config.CONFIG_SECTION_NAME: activity_config.schema,
        resource_manager_config.CONFIG_SECTION_NAME: resource_manager_config.schema,
        #TODO: s3_config.CONFIG_SECTION_NAME: s3_config.schema
        #TODO: enable when sockets are refactored
        # BELOW HERE minimal sections until more options are needed
        addon_section("reverse_proxy", optional=True): minimal_addon_schema(),
        addon_section("application_proxy", optional=True): minimal_addon_schema(),
        addon_section("users", optional=True): minimal_addon_schema(),
        addon_section("studies_access", optional=True): minimal_addon_schema()
    })

    section_names = [k.name for k in schema.keys]
    assert len(section_names) == len(set(section_names)), "Found repeated section names in %s" % section_names

    return schema


CLI_DEFAULT_CONFIGFILE = 'server-defaults.yaml'
app_schema = create_schema() # TODO: rename as schema

assert resources.exists( 'config/' + CLI_DEFAULT_CONFIGFILE )
