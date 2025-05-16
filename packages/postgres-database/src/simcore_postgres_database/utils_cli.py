import json
import json.decoder
import logging
import os
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from typing import Final

import click
import docker.client
from alembic.config import Config as AlembicConfig

from .utils import build_url
from .utils_migration import create_basic_config

DISCOVERED_CACHE: Final[str] = os.path.expanduser(
    "~/.simcore_postgres_database_cache.json"
)


log = logging.getLogger("root")


def _safe(if_fails_return=False):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kargs):
            try:
                return func(*args, **kargs)
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
    client = docker.client.from_env()
    services = [
        s for s in client.services.list() if service_name in getattr(s, "name", "")
    ]
    if not services:
        msg = f"Cannot find published port for service '{service_name}'. Probably services still not up"
        raise RuntimeError(msg)
    service_endpoint = services[0].attrs["Endpoint"]

    if "Ports" not in service_endpoint or not service_endpoint["Ports"]:
        msg = f"Cannot find published port for service '{service_name}' in endpoint. Probably services still not up"
        raise RuntimeError(msg)

    published_port = service_endpoint["Ports"][0]["PublishedPort"]
    return int(published_port)


def load_cache(*, raise_if_error=False) -> dict:
    try:
        with open(DISCOVERED_CACHE) as fh:
            cfg = json.load(fh)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        if raise_if_error:
            raise
        return {}
    return dict(cfg)


def reset_cache():
    if os.path.exists(DISCOVERED_CACHE):
        os.remove(DISCOVERED_CACHE)
        click.echo(f"Removed {DISCOVERED_CACHE}")


def get_alembic_config_from_cache(
    force_cfg: dict | None = None,
) -> AlembicConfig | None:
    """
    Creates alembic config from cfg or cache

    Returns None if cannot build url (e.g. if user requires a cache that does not exists)
    """

    # build url
    try:
        cfg = force_cfg if force_cfg else load_cache(raise_if_error=True)

        url = build_url(**cfg)
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "Cannot open cache or cannot build URL", exc_info=True, stack_info=True
        )
        click.echo("Invalid database config, please run discover first", err=True)
        reset_cache()
        return None

    # build config
    config = create_basic_config()
    config.set_main_option("sqlalchemy.url", str(url))
    return config
