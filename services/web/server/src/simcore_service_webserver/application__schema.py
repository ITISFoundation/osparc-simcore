""" app's configuration

    This module loads the schema defined by every subsystem and injects it in the
    application's configuration scheams

    It was designed in a similar fashion to the setup protocol of the application
    where every subsystem is imported and queried in a specific order. The application
    depends on the subsystem and not the other way around.

    The app configuration is created before the application instance exists.

"""
import logging
from pathlib import Path
from typing import Dict

import trafaret as T
from trafaret_config.simple import read_and_validate

from . import (
    catalog__schema,
    db__schema,
    email__schema,
    rest__schema,
    session__schema,
    storage__schema,
    tracing,
)
from ._resources import resources
from .activity import _schema as activity__schema
from .director import _schema as director__schema
from .login import _schema as login__schema
from .projects import _schema as projects__schema
from .resource_manager import _schema as resource_manager__schema
from .socketio import _schema as socketio__schema

log = logging.getLogger(__name__)

CLI_DEFAULT_CONFIGFILE = "server-defaults.yaml"
assert resources.exists("config/" + CLI_DEFAULT_CONFIGFILE)  # nosec


def addon_section(name: str, optional: bool = False) -> T.Key:
    if optional:
        return T.Key(name, default=dict(enabled=True), optional=optional)
    return T.Key(name)


def minimal_addon_schema() -> T.Dict:
    return T.Dict({T.Key("enabled", default=True, optional=True): T.Bool()})


def create_schema() -> T.Dict:
    """
    Build schema for the configuration's file
    by aggregating all the subsystem configurations
    """
    # pylint: disable=protected-access
    schema = T.Dict(
        {
            "version": T.String(),
            "main": T.Dict(
                {
                    "host": T.IP,
                    "port": T.ToInt(),
                    "log_level": T.Enum(*logging._nameToLevel.keys()),
                    "testing": T.Bool(),
                    T.Key("studies_access_enabled", default=False): T.Or(
                        T.Bool(), T.ToInt
                    ),
                }
            ),
            addon_section(tracing.CONFIG_SECTION_NAME, optional=True): tracing.schema,
            db__schema.CONFIG_SECTION_NAME: db__schema.schema,
            director__schema.CONFIG_SECTION_NAME: director__schema.schema,
            rest__schema.CONFIG_SECTION_NAME: rest__schema.schema,
            projects__schema.CONFIG_SECTION_NAME: projects__schema.schema,
            email__schema.CONFIG_SECTION_NAME: email__schema.schema,
            storage__schema.CONFIG_SECTION_NAME: storage__schema.schema,
            addon_section(
                login__schema.CONFIG_SECTION_NAME, optional=True
            ): login__schema.schema,
            addon_section(
                socketio__schema.CONFIG_SECTION_NAME, optional=True
            ): socketio__schema.schema,
            session__schema.CONFIG_SECTION_NAME: session__schema.schema,
            activity__schema.CONFIG_SECTION_NAME: activity__schema.schema,
            resource_manager__schema.CONFIG_SECTION_NAME: resource_manager__schema.schema,
            # BELOW HERE minimal sections until more options are needed
            addon_section("catalog", optional=True): catalog__schema.schema,
            addon_section("clusters", optional=True): minimal_addon_schema(),
            addon_section("computation", optional=True): minimal_addon_schema(),
            addon_section("diagnostics", optional=True): minimal_addon_schema(),
            addon_section("director-v2", optional=True): minimal_addon_schema(),
            addon_section("exporter", optional=True): minimal_addon_schema(),
            addon_section("groups", optional=True): minimal_addon_schema(),
            addon_section("meta_modeling", optional=True): minimal_addon_schema(),
            addon_section("products", optional=True): minimal_addon_schema(),
            addon_section("publications", optional=True): minimal_addon_schema(),
            addon_section("redis", optional=True): minimal_addon_schema(),
            addon_section("remote_debug", optional=True): minimal_addon_schema(),
            addon_section("security", optional=True): minimal_addon_schema(),
            addon_section("statics", optional=True): minimal_addon_schema(),
            addon_section("studies_access", optional=True): minimal_addon_schema(),
            addon_section("studies_dispatcher", optional=True): minimal_addon_schema(),
            addon_section("tags", optional=True): minimal_addon_schema(),
            addon_section("users", optional=True): minimal_addon_schema(),
            addon_section("version_control", optional=True): minimal_addon_schema(),
        }
    )

    section_names = [k.name for k in schema.keys]

    # fmt: off
    assert len(section_names) == len(set(section_names)), f"Found repeated section names in {section_names}"  # nosec
    # fmt: on

    return schema


def load_default_config(environs=None) -> Dict:
    filepath: Path = resources.get_path(f"config/{CLI_DEFAULT_CONFIGFILE}")
    return read_and_validate(filepath, trafaret=app_schema, vars=environs)


app_schema = create_schema()
