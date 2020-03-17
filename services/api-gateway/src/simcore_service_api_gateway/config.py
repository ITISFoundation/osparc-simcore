"""

    NOTE: CONS of programmatic config
    - not testing-friendly since variables set upon import. Must reload when fixture is setup


TODO: convert in pydantic Data
"""
import logging
import os
from typing import Dict

from .utils.helpers import to_bool

# DOCKER
is_containerized: bool = "SC_BOOT_MODE" in os.environ

# LOGGING
log_level_name = os.environ.get("LOGLEVEL", "debug").upper()
log_level = getattr(logging, log_level_name.upper())
log_formatter = logging.Formatter('%(levelname)s:  %(message)s [%(name)s:%(lineno)d]')

logging.root.setLevel(log_level)
if logging.root.handlers:
    logging.root.handlers[0].setFormatter(log_formatter)


# TEST MODE
is_testing_enabled: bool = to_bool(os.environ.get("TESTING", "true"))


# POSGRESS API
postgres_cfg: Dict = {
    'user': os.environ.get("POSTGRES_USER", "test"),
    'password': os.environ.get("POSTGRES_PASSWORD", "test"),
    'database': os.environ.get("POSTGRES_DB", "test"),
    'host':  os.environ.get("POSTGRES_HOST", "localhost"),
    'port': int(os.environ.get("POSTGRES_PORT", "5432"))
}
postgres_dsn: str = "postgresql://{user}:{password}@{host}:{port}/{database}".format(**postgres_cfg)
postgres_cfg: Dict = {**postgres_cfg, 'uri':postgres_dsn}


# SERVER
# NOTE: https://www.uvicorn.org/settings/
uvicorn_settings: Dict = {
    'host':"0.0.0.0" if is_containerized else "127.0.0.1",
    'port':8000,
    'log_level': log_level_name.lower()
}

# APPLICATION
app_context: Dict = {} # FIXME: hate globals!
