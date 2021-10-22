import json
import json.decoder
import logging
import os
import sys
from copy import deepcopy
from functools import wraps
from pathlib import Path
from typing import Callable, Dict, Final, Optional

import click
import docker
from alembic import __version__ as __alembic_version__
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from simcore_postgres_database.utils import build_url

_CURRENT_DIR = Path(
    sys.argv[0] if __name__ == "__main__" else __file__
).parent.resolve()

DEFAULT_INI: Final[Path] = _CURRENT_DIR / "alembic.ini"
MIGRATION_DIR: Final[Path] = _CURRENT_DIR / "migration"

DISCOVERED_CACHE: Final[str] = os.path.expanduser(
    "~/.simcore_postgres_database_cache.json"
)

RevisionID = str

log = logging.getLogger("root")


def _create_basic_config() -> AlembicConfig:
    config = AlembicConfig(file_=str(DEFAULT_INI))
    config.set_main_option("script_location", str(MIGRATION_DIR))
    return config


def _safe(if_fails_return=False):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kargs):
            try:
                res = func(*args, **kargs)
                return res
            except RuntimeError as err:
                log.info(
                    "%s failed:  %s",
                    func.__name__,
                    str(err),
                    exc_info=True,
                    stack_info=True,
                )
            except Exception:  # pylint: disable=broad-except
                log.info(
                    "%s failed unexpectedly",
                    func.__name__,
                    exc_info=True,
                    stack_info=True,
                )
            return deepcopy(if_fails_return)  # avoid issues with default mutables

        return wrapper

    return decorator


@_safe(if_fails_return=None)
def get_service_published_port(service_name: str) -> int:
    client = docker.from_env()
    services = [
        s for s in client.services.list() if service_name in getattr(s, "name", "")
    ]
    if not services:
        raise RuntimeError(
            "Cannot find published port for service '%s'. Probably services still not up"
            % service_name
        )
    service_endpoint = services[0].attrs["Endpoint"]

    if "Ports" not in service_endpoint or not service_endpoint["Ports"]:
        raise RuntimeError(
            "Cannot find published port for service '%s' in endpoint. Probably services still not up"
            % service_name
        )

    published_port = service_endpoint["Ports"][0]["PublishedPort"]
    return int(published_port)


def load_cache(*, raise_if_error=False) -> Dict:
    try:
        with open(DISCOVERED_CACHE) as fh:
            cfg = json.load(fh)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        if raise_if_error:
            raise
        return {}
    return cfg


def reset_cache():
    if os.path.exists(DISCOVERED_CACHE):
        os.remove(DISCOVERED_CACHE)
        click.echo("Removed %s" % DISCOVERED_CACHE)


def get_alembic_config_from_cache(
    force_cfg: Optional[Dict] = None,
) -> Optional[AlembicConfig]:
    """
    Creates alembic config from cfg or cache

    Returns None if cannot build url (e.g. if user requires a cache that does not exists)
    """

    # build url
    try:
        if force_cfg:
            cfg = force_cfg
        else:
            cfg = load_cache(raise_if_error=True)

        url = build_url(**cfg)
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "Cannot open cache or cannot build URL", exc_info=True, stack_info=True
        )
        click.echo("Invalid database config, please run discover first", err=True)
        reset_cache()
        return None

    # build config
    config = _create_basic_config()
    config.set_main_option("sqlalchemy.url", str(url))
    return config


def get_current_head() -> RevisionID:
    """Return the current head revision.

    If the script directory has multiple heads
    due to branching, an error is raised;
    """
    config = _create_basic_config()
    script = ScriptDirectory.from_config(config)

    head = script.get_current_head()
    assert head  # nosec
    return head
