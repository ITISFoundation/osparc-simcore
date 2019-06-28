import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import alembic.command
import click
import docker
import sqlalchemy as sa
from alembic import __version__ as __alembic_version__
from alembic.config import Config as AlembicConfig

from simcore_postgres_database.settings import DSN


alembic_version = tuple([int(v) for v in __alembic_version__.split('.')[0:3]])

log = logging.getLogger(__name__)

here = Path( sys.argv[0] if __name__ == "__main__" else __file__ ).parent.resolve()
default_ini = here / 'alembic.ini'
migration_dir = here / 'migration'
discovered_cache = os.path.join( tempfile.mkdtemp(__name__), ".discovered_cache-ignore.json")

def safe(if_fails_return=False):
    def decorate(func):
        def safe_func(*args, **kargs):
            try:
                res = func(*args, **kargs)
                return res
            except RuntimeError as err:
                log.info("%s failed:  %s", func.__name__, str(err))
            except Exception: #pylint: disable=broad-except
                log.info("%s failed unexpectedly", func.__name__, exc_info=True)
            return if_fails_return
        return safe_func
    return decorate

#@retry(wait=wait_fixed(0.1), stop=stop_after_delay(60))
@safe()
def ping(url):
    """checks whether database is responsive"""
    engine = sa.create_engine(url)
    conn = engine.connect()
    conn.close()
    return True


@safe(if_fails_return=None)
def get_service_published_port(service_name: str) -> int:
    client = docker.from_env()
    services = [x for x in client.services.list() if service_name in x.name]
    if not services:
        raise RuntimeError("Cannot find published port for service '%s'. Probably services still not up" % service_name)
    service_endpoint = services[0].attrs["Endpoint"]

    if "Ports" not in service_endpoint or not service_endpoint["Ports"]:
        raise RuntimeError("Cannot find published port for service '%s' in endpoint. Probably services still not up" % service_name)

    published_port = service_endpoint["Ports"][0]["PublishedPort"]
    return int(published_port)

def get_config():
    with open(discovered_cache) as fh:
        cfg = json.load(fh)

    config = AlembicConfig(default_ini)
    config.set_main_option('script_location', str(migration_dir))
    config.set_main_option('sqlalchemy.url', DSN.format(**cfg))
    return config

# CLI -----------------------------------------------

@click.group()
def main():
    """ Simplified CLI for database migration with alembic"""


@main.command()
def clean():
    if os.path.exists(discovered_cache):
        os.remove(discovered_cache)
        click.echo("Removed %s" % discovered_cache)

@main.command()
def discover():
    """ Discovers active databases """
    click.echo('Discovering database ...')
    # TODO: add guess via CLI params, e.g. user and password
    # TODO: if multiple candidates online, then query user to select

    # First guess is via environ variables
    cfg = dict(
        user = os.getenv('POSTGRES_USER'),
        password = os.getenv('POSTGRES_PASSWORD'),
        host = os.getenv('POSTGRES_HOST'),
        port = os.getenv('POSTGRES_PORT'),
        database = os.getenv('POSTGRES_DB')
    )
    url = DSN.format(**cfg)
    try:
        click.echo("Trying %s ..." % url)

        if not all(cfg.values()) or not ping(url):
            cfg['port'] = port = get_service_published_port(cfg['host'])
            cfg['host'] = "127.0.0.1"
            url = DSN.format(**cfg)

            click.echo("Trying %s ..." % url)
            if port is None or not ping(url):
                raise RuntimeError

        dumps = json.dumps(cfg, sort_keys=True, indent=4)
        click.echo(f"Responded. \ndiscovered_cache config: {dumps}")

        with open(discovered_cache, 'w') as fh:
            fh.write(dumps)

    except RuntimeError:
        clean()
        click.echo("Database not found")





@main.command()
@click.option('-m', 'message')
def review(message):
    """Auto-generates a new revison

        alembic revision --autogenerate -m "first tables"
    """
    click.echo('Auto-generates revision based on changes ')

    config = get_config()
    alembic.command.revision(config, message,
        autogenerate=True, sql=False,
        head='head', splice=False, branch_label=None, version_path=None,
        rev_id=None)


@main.command()
@click.argument('revision', default='head')
def upgrade(revision):
    """Upgrades target database to a given revision"""
    click.echo(f'Upgrading database to {revision} ...')
    config = get_config()
    alembic.command.upgrade(config, revision, sql=False, tag=None)




if __name__ == '__main__':
    main()
