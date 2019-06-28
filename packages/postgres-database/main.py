import json
import logging
import os
import sys
from copy import deepcopy
from pathlib import Path

import alembic.command
import click
import docker
import sqlalchemy as sa
from alembic import __version__ as __alembic_version__
from alembic.config import Config as AlembicConfig
#from alembic.util import CommandError

from simcore_postgres_database.settings import DSN, db_config, sqlalchemy_url

alembic_version = tuple([int(v) for v in __alembic_version__.split('.')[0:3]])
log = logging.getLogger(__name__)

here = Path( sys.argv[0] if __name__ == "__main__" else __file__ ).parent.resolve()

DISCOVERED = ".discovered-ignore.json"
default_ini = here / 'alembic.ini'
migration_dir = here / 'migration'

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




@click.group()
def cli():
    """ Wraps alembic CLI to simplify database migration

    """



@cli.command()
def discover():
    """ Discovers active databases

        - dumps first match
        -
    """
    click.echo('Discovering database ...')

    try:
        # db_config comes from configuration variables
        cfg = deepcopy(db_config)
        url = DSN.format(**cfg)

        click.echo("Trying %s ..." % url)
        if not ping(url):
            cfg['port'] = port = get_service_published_port(cfg['host'])
            cfg['host'] = "127.0.0.1"
            url = DSN.format(**cfg)

            click.echo("Trying %s ..." % url)
            if port is None or not ping(url):
                raise RuntimeError

        dumps = json.dumps(cfg, sort_keys=True, indent=4)
        click.echo(f"Responded. \nDiscovered config: {dumps}")

        with open(DISCOVERED, 'w') as fh:
            fh.write(dumps)

    except RuntimeError:
        if os.path.exists(DISCOVERED):
            os.remove(DISCOVERED)
        click.echo("Database not found")


def get_config():
    with open(DISCOVERED) as fh:
        cfg = json.load(fh)

    config = AlembicConfig(default_ini)

    config.set_main_option('script_location', str(migration_dir))
    config.set_main_option('sqlalchemy.url', DSN.format(**cfg))
    return config


@cli.command()
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


@cli.command()
@click.argument('revision', default='head')
def upgrade(revision):
    """Upgrades target database to a given revision"""
    click.echo(f'Upgrading database to {revision} ...')
    config = get_config()
    alembic.command.upgrade(config, revision, sql=False, tag=None)


if __name__ == '__main__':
    cli()
