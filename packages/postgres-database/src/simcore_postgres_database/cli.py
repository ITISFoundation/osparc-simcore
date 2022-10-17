""" command line interface for migration

"""
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import

import json
import json.decoder
import logging
import os
from logging.config import fileConfig
from typing import Optional

import alembic.command
import click
from alembic import __version__ as __alembic_version__
from simcore_postgres_database.models import *
from simcore_postgres_database.utils import (
    build_url,
    hide_dict_pass,
    hide_url_pass,
    raise_if_not_responsive,
)
from simcore_postgres_database.utils_cli import (
    DISCOVERED_CACHE,
    get_alembic_config_from_cache,
    get_service_published_port,
    load_cache,
    reset_cache,
)
from simcore_postgres_database.utils_migration import DEFAULT_INI
from tenacity import Retrying
from tenacity.after import after_log
from tenacity.wait import wait_fixed

ALEMBIC_VERSION = tuple(int(v) for v in __alembic_version__.split(".")[0:3])
DEFAULT_HOST = "postgres"
DEFAULT_PORT = 5432
DEFAULT_DB = "simcoredb"

log = logging.getLogger("root")

if __name__ == "__main__":
    # swallows up all log messages from tests
    # only enable it during cli invocation
    fileConfig(DEFAULT_INI)


@click.group()
def main():
    """Simplified CLI for database migration with alembic"""


@main.command()
@click.option("--user", "-u")
@click.option("--password", "-p")
@click.option("--host")
@click.option("--port", type=int)
@click.option("--database", "-d")
def discover(**cli_inputs) -> Optional[dict]:
    """Discovers databases and caches configs in ~/.simcore_postgres_database.json (except if --no-cache)"""
    # NOTE: Do not add defaults to user, password so we get a chance to ping urls
    # TODO: if multiple candidates online, then query user to select

    click.echo("Discovering database ...")
    cli_cfg = {key: value for key, value in cli_inputs.items() if value is not None}

    # tests different urls

    def _test_cached() -> dict:
        """Tests cached configuration"""
        cfg = load_cache(raise_if_error=True)
        cfg.update(cli_cfg)  # overrides
        return cfg

    def _test_env() -> dict:
        """Tests environ variables"""
        cfg = {
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
            "host": os.getenv("POSTGRES_HOST", DEFAULT_HOST),
            "port": int(os.getenv("POSTGRES_PORT") or DEFAULT_PORT),
            "database": os.getenv("POSTGRES_DB", DEFAULT_DB),
        }
        cfg.update(cli_cfg)
        return cfg

    def _test_swarm() -> dict:
        """Tests published port in swarm from host"""
        cfg = _test_env()
        cfg["host"] = "127.0.0.1"
        cfg["port"] = get_service_published_port(cli_cfg.get("host", DEFAULT_HOST))
        cfg.setdefault("database", DEFAULT_DB)
        return cfg

    for test in [_test_cached, _test_env, _test_swarm]:
        try:
            click.echo("-> {0.__name__}: {0.__doc__}".format(test))

            cfg: dict = test()
            cfg.update(cli_cfg)  # CLI always overrides
            url = build_url(**cfg)

            click.echo(f"ping {test.__name__}: {hide_url_pass(url)} ...")
            raise_if_not_responsive(url, verbose=False)

            print("Saving config ")
            click.echo(f"Saving config at {DISCOVERED_CACHE}: {hide_dict_pass(cfg)}")
            with open(DISCOVERED_CACHE, "wt") as fh:
                json.dump(cfg, fh, sort_keys=True, indent=4)

            print("Saving config at ")
            click.secho(
                f"{test.__name__} succeeded: {hide_url_pass(url)} is online",
                blink=False,
                bold=True,
                fg="green",
            )

            return cfg

        except Exception as err:  # pylint: disable=broad-except
            inline_msg = str(err).replace("\n", ". ")
            click.echo(f"<- {test.__name__} failed : {inline_msg}")

    reset_cache()
    click.secho("Sorry, database not found !!", blink=False, bold=True, fg="red")
    return None


@main.command()
def info():
    """Displays discovered config and other alembic infos"""
    click.echo("Using alembic {}.{}.{}".format(*ALEMBIC_VERSION))

    cfg = load_cache()
    click.echo(f"Saved config: {hide_dict_pass(cfg)} @ {DISCOVERED_CACHE}")
    config = get_alembic_config_from_cache(cfg)
    if config:
        click.echo("Revisions history ------------")
        alembic.command.history(config)
        click.echo("Current version: -------------")
        alembic.command.current(config, verbose=True)


@main.command()
def clean():
    """Clears discovered database"""
    reset_cache()


@main.command()
def upgrade_and_close():
    """Used in migration service program to discover, upgrade and close"""

    for attempt in Retrying(wait=wait_fixed(5), after=after_log(log, logging.ERROR)):
        with attempt:
            if not discover.callback():
                raise Exception("Postgres db was not discover")

    # FIXME: if database is not stampped!?
    try:
        info.callback()
        upgrade.callback(revision="head")
        info.callback()
    except Exception:  # pylint: disable=broad-except
        log.exception("Unable to upgrade")

    click.echo("I did my job here. Bye!")


# Overrides Alembic CLI  ------------


@main.command()
@click.option("-m", "message")
def review(message):
    """Auto-generates a new revison. Equivalent to `alembic revision --autogenerate -m "first tables"`"""
    click.echo("Auto-generates revision based on changes ")

    config = get_alembic_config_from_cache()
    if config:
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
    else:
        raise ValueError("Missing config")


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
    config = get_alembic_config_from_cache()
    if config:
        alembic.command.upgrade(config, revision, sql=False, tag=None)
    else:
        raise ValueError("Missing config")


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
    config = get_alembic_config_from_cache()
    if config:
        alembic.command.downgrade(config, str(revision), sql=False, tag=None)
    else:
        raise ValueError("Missing config")


@main.command()
@click.argument("revision", default="head")
def stamp(revision):
    """Stamps the database with a given revision; does not run any migration"""
    click.echo(f"Stamps db to {revision} ...")
    config = get_alembic_config_from_cache()
    if config:
        alembic.command.stamp(config, revision, sql=False, tag=None)
    else:
        raise ValueError("Missing config")
