""" command line interface for migration

"""
# pylint: disable=broad-except

import json
import logging
import os
import sys
from copy import deepcopy
from logging.config import fileConfig
from pathlib import Path

import alembic.command
import click
import docker
from alembic import __version__ as __alembic_version__
from alembic.config import Config as AlembicConfig

from simcore_postgres_database.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from simcore_postgres_database.utils import build_url, raise_if_not_responsive

alembic_version = tuple([int(v) for v in __alembic_version__.split(".")[0:3]])

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.resolve()
default_ini = current_dir / "alembic.ini"
migration_dir = current_dir / "migration"
discovered_cache = os.path.expanduser("~/.simcore_postgres_database_cache.json")

log = logging.getLogger("root")
fileConfig(default_ini)


def safe(if_fails_return=False):
    def decorate(func):
        def safe_func(*args, **kargs):
            try:
                res = func(*args, **kargs)
                return res
            except RuntimeError as err:
                log.info("%s failed:  %s", func.__name__, str(err))
            except Exception:
                log.info("%s failed unexpectedly", func.__name__, exc_info=True)
            return deepcopy(if_fails_return)  # avoid issues with default mutables

        return safe_func

    return decorate


@safe(if_fails_return=None)
def _get_service_published_port(service_name: str) -> int:
    client = docker.from_env()
    services = [x for x in client.services.list() if service_name in x.name]
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


def _get_alembic_config(cfg=None):
    try:
        if not cfg:
            cfg = _load_cache() or {}
        url = build_url(**cfg)
    except Exception:
        click.echo("Invalid database config, please run discover", err=True)
        _reset_cache()
        return {}

    config = AlembicConfig(default_ini)
    config.set_main_option("script_location", str(migration_dir))
    config.set_main_option("sqlalchemy.url", str(url))
    return config


@safe(if_fails_return={})
def _load_cache():
    with open(discovered_cache) as fh:
        cfg = json.load(fh)
    return cfg


def _reset_cache():
    if os.path.exists(discovered_cache):
        os.remove(discovered_cache)
        click.echo("Removed %s" % discovered_cache)


# CLI -----------------------------------------------
DEFAULT_HOST = "postgres"
DEFAULT_PORT = 5432
DEFAULT_DB = "simcoredb"


@click.group()
def main():
    """ Simplified CLI for database migration with alembic """




@main.command()
@click.option("--user", "-u")
@click.option("--password", "-p")
@click.option("--host")
@click.option("--port", type=int)
@click.option("--database", "-d")
def discover(**cli_inputs):
    """ Discovers databases and caches configs in ~/.simcore_postgres_database.json (except if --no-cache)"""
    # NOTE: Do not add defaults to user, password so we get a chance to ping urls
    # TODO: if multiple candidates online, then query user to select

    click.echo(f"Discovering database ...")
    cli_cfg = {key: value for key, value in cli_inputs.items() if value is not None}

    def _test_cached():
        """Tests cached configuration """
        cfg = _load_cache() or {}
        if cfg:
            cfg.update(cli_cfg)  # overrides
        return cfg

    def _test_env():
        """Tests environ variables """
        cfg = {
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
            "host": os.getenv("POSTGRES_HOST", DEFAULT_HOST),
            "port": int(os.getenv("POSTGRES_PORT") or DEFAULT_PORT),
            "database": os.getenv("POSTGRES_DB", DEFAULT_DB),
        }
        cfg.update(cli_cfg)
        return cfg

    def _test_swarm():
        """Tests published port in swarm from host """
        cfg = _test_env()
        cfg["host"] = "127.0.0.1"
        cfg["port"] = _get_service_published_port(cli_cfg.get("host", DEFAULT_HOST))
        cfg.setdefault("database", DEFAULT_DB)
        return cfg

    for test in [_test_cached, _test_env, _test_swarm]:
        try:
            click.echo("-> {0.__name__}: {0.__doc__}".format(test))

            cfg = test()
            cfg.update(cli_cfg)  # CLI always overrides
            url = build_url(**cfg)

            click.echo(" ping {0.__name__}: {1} ...".format(test, url))

            raise_if_not_responsive(url)
            with open(discovered_cache, "w") as fh:
                json.dump(cfg, fh, sort_keys=True, indent=4)

            click.echo(f"Saved config at{discovered_cache}: {cfg}")
            click.secho(
                f"{test.__name__} succeeded: {url} is online",
                blink=False,
                bold=True,
                fg="green",
            )

            return

        except Exception as err:
            inline_msg = str(err).replace("\n", ". ")
            click.echo("<- {0.__name__} failed : {1}".format(test, inline_msg))

    _reset_cache()
    click.secho("Sorry, database not found !!", blink=False, bold=True, fg="red")


@main.command()
def info():
    """ Displays discovered config and other alembic infos"""
    click.echo("Using alembic {}.{}.{}".format(*alembic_version))

    cfg = _load_cache()
    click.echo(f"Saved config: {cfg} @ {discovered_cache}")
    config = _get_alembic_config(cfg)
    if config:
        click.echo("Revisions history ------------")
        alembic.command.history(config)
        click.echo("Current version: -------------")
        alembic.command.current(config, verbose=True)


@main.command()
def clean():
    """ Clears discovered database """
    _reset_cache()


# Bypasses alembic CLI into a reduced version  ------------

@main.command()
@click.option("-m", "message")
def review(message):
    """Auto-generates a new revison. Equivalent to `alembic revision --autogenerate -m "first tables"`
    """
    click.echo("Auto-generates revision based on changes ")

    config = _get_alembic_config()
    alembic.command.revision(
        config,
        message,
        autogenerate=True,
        sql=False,
        head="head",
        splice=False,
        branch_label=None,
        version_path=None,
        rev_id=None,
    )


@main.command()
@click.argument("revision", default="head")
def upgrade(revision):
    """Upgrades target database to a given revision

        Say we have revision ae1027a6acf

        Absolute migration:
            sc-pg upgrade ae10

        Relative to current:
            sc-pg upgrade +2
            sc-pg downgrade -- -1
            sc-pg upgrade ae10+2

    """
    click.echo(f"Upgrading database to {revision} ...")
    config = _get_alembic_config()
    alembic.command.upgrade(config, revision, sql=False, tag=None)


@main.command()
@click.argument("revision", default="-1")
def downgrade(revision):
    """Revert target database to a given revision

        Say we have revision ae1027a6acf

        Absolute migration:
            sc-pg upgrade ae10

        Relative to current:
            sc-pg upgrade +2
            sc-pg downgrade -- -1
            sc-pg upgrade ae10+2
    """
    # https://click.palletsprojects.com/en/3.x/arguments/#argument-like-options
    click.echo(f"Downgrading database to current-{revision} ...")
    config = _get_alembic_config()
    alembic.command.downgrade(config, str(revision), sql=False, tag=None)


@main.command()
@click.argument("revision", default="head")
def stamp(revision):
    """Stamps the database with a given revision; does not run any migration"""
    click.echo(f"Stamps db to {revision} ...")
    config = _get_alembic_config()
    alembic.command.stamp(config, revision, sql=False, tag=None)
