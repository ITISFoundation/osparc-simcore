"""

    NOTE: CONS of programmatic config
    - not testing-friendly since variables set upon import. Must reload when fixture is setup
"""
import logging
import os

from .utils.helpers import cast_to_bool

# DOCKER
is_container_environ: bool = "SC_BOOT_MODE" in os.environ
is_devel = os.environ.get("SC_BUILD_TARGET") == "development"
is_prod  = os.environ.get("SC_BUILD_TARGET") == "production"


# LOGGING
log_level_name = os.environ.get("LOGLEVEL", "debug").upper()
log_level = getattr(logging, log_level_name.upper())
log_formatter = logging.Formatter("%(levelname)s:  %(message)s [%(name)s:%(lineno)d]")

logging.root.setLevel(log_level)
if logging.root.handlers:
    logging.root.handlers[0].setFormatter(log_formatter)


# TEST MODE
is_testing_enabled: bool = cast_to_bool(os.environ.get("TESTING", "true"))


# POSGRESS API
postgres_cfg: dict = {
    "user": os.environ.get("POSTGRES_USER", "test"),
    "password": os.environ.get("POSTGRES_PASSWORD", "test"),
    "database": os.environ.get("POSTGRES_DB", "test"),
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", "5432")),
}
postgres_dsn: str = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
    **postgres_cfg
)
postgres_cfg: dict = {**postgres_cfg, "uri": postgres_dsn}
init_tables: bool = cast_to_bool(os.environ.get("POSTGRES_INIT_TABLES", "true" if is_devel else "false"))

# SERVER
# NOTE: https://www.uvicorn.org/settings/
uvicorn_settings: dict = {
    "host": "0.0.0.0" if is_container_environ else "127.0.0.1",  # nosec
    "port": 8000,
    "log_level": log_level_name.lower(),
}

# APPLICATION
app_context: dict = {}  # FIXME: hate globals!
