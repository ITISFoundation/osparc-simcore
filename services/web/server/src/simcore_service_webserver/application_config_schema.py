import logging
from pathlib import Path
from typing import Dict

import trafaret as T
from simcore_service_webserver import tracing_config_schema
from trafaret_config.simple import read_and_validate

from . import email_config_schema, storage_config_schema, tracing_config_schema
from .activity import config_schema as activity_config_schema
from .director import config_schema as director_config_schema
from .login import config_schema as login_config_schema
from .resource_manager import config_schema as resource_manager_config_schema
from .resources import resources

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
            addon_section(
                tracing_config_schema.CONFIG_SECTION_NAME, optional=True
            ): tracing_config_schema.schema,
            # db_config_schema.CONFIG_SECTION_NAME: db_config_schema.schema,
            director_config_schema.CONFIG_SECTION_NAME: director_config_schema.schema,
            email_config_schema.CONFIG_SECTION_NAME: email_config_schema.schema,
            storage_config_schema.CONFIG_SECTION_NAME: storage_config_schema.schema,
            addon_section(
                login_config_schema.CONFIG_SECTION_NAME, optional=True
            ): login_config_schema.schema,
            activity_config_schema.CONFIG_SECTION_NAME: activity_config_schema.schema,
            resource_manager_config_schema.CONFIG_SECTION_NAME: resource_manager_config_schema.schema,
            # BELOW HERE minimal sections until more options are needed
            addon_section("clusters", optional=True): minimal_addon_schema(),
            addon_section("computation", optional=True): minimal_addon_schema(),
            addon_section("diagnostics", optional=True): minimal_addon_schema(),
            addon_section("director-v2", optional=True): minimal_addon_schema(),
            addon_section("exporter", optional=True): minimal_addon_schema(),
            addon_section("groups", optional=True): minimal_addon_schema(),
            addon_section("products", optional=True): minimal_addon_schema(),
            addon_section("publications", optional=True): minimal_addon_schema(),
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
