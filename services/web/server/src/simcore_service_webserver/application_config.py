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
from aiohttp.web import Application
from models_library.basic_types import LogLevel, PortInt
from pydantic import BaseSettings, Field
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.config_schema_utils import addon_section, minimal_addon_schema
from trafaret_config.simple import read_and_validate

from . import (
    catalog_config,
    db_config,
    email_config,
    rest_config,
    session_config,
    storage_config,
    tracing,
)
from .activity import config as activity_config
from .director import config as director_config
from .login import config as login_config
from .projects import config as projects_config
from .resource_manager import config as resource_manager_config
from .resources import resources
from .socketio import config as socketio_config

log = logging.getLogger(__name__)

CLI_DEFAULT_CONFIGFILE = "server-defaults.yaml"
assert resources.exists("config/" + CLI_DEFAULT_CONFIGFILE)  # nosec


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
                    "client_outdir": T.String(),
                    "log_level": T.Enum(*logging._nameToLevel.keys()),
                    "testing": T.Bool(),
                    T.Key("studies_access_enabled", default=False): T.Or(
                        T.Bool(), T.ToInt
                    ),
                }
            ),
            addon_section(tracing.tracing_section_name, optional=True): tracing.schema,
            db_config.CONFIG_SECTION_NAME: db_config.schema,
            director_config.CONFIG_SECTION_NAME: director_config.schema,
            rest_config.CONFIG_SECTION_NAME: rest_config.schema,
            projects_config.CONFIG_SECTION_NAME: projects_config.schema,
            email_config.CONFIG_SECTION_NAME: email_config.schema,
            storage_config.CONFIG_SECTION_NAME: storage_config.schema,
            addon_section(
                login_config.CONFIG_SECTION_NAME, optional=True
            ): login_config.schema,
            addon_section(
                socketio_config.CONFIG_SECTION_NAME, optional=True
            ): socketio_config.schema,
            session_config.CONFIG_SECTION_NAME: session_config.schema,
            activity_config.CONFIG_SECTION_NAME: activity_config.schema,
            resource_manager_config.CONFIG_SECTION_NAME: resource_manager_config.schema,
            # BELOW HERE minimal sections until more options are needed
            addon_section("diagnostics", optional=True): minimal_addon_schema(),
            addon_section("users", optional=True): minimal_addon_schema(),
            addon_section("groups", optional=True): minimal_addon_schema(),
            addon_section("tags", optional=True): minimal_addon_schema(),
            addon_section("publications", optional=True): minimal_addon_schema(),
            addon_section("catalog", optional=True): catalog_config.schema,
            addon_section("products", optional=True): minimal_addon_schema(),
            addon_section("computation", optional=True): minimal_addon_schema(),
            addon_section("director-v2", optional=True): minimal_addon_schema(),
            addon_section("studies_access", optional=True): minimal_addon_schema(),
            addon_section("studies_dispatcher", optional=True): minimal_addon_schema(),
            addon_section("exporter", optional=True): minimal_addon_schema(),
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


class MainSettings(BaseSettings):
    host: str = "0.0.0.0"  # nosec
    port: PortInt = 8080
    client_outdir: Path = Field(..., env="SIMCORE_WEB_OUTDIR")
    log_level: LogLevel = Field(LogLevel.INFO, env="WEBSERVER_LOGLEVEL")
    testing: bool = False
    studies_access_enabled: bool = False

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_"


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY]["main"]
    _settings = MainSettings(**cfg)
    return cfg
