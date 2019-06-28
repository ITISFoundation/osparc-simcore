""" command line interface for migration

"""
#pylint: disable=broad-except

import json
import logging
import os
import sys
import tempfile
from logging.config import fileConfig
from pathlib import Path

import alembic.command
import click
import docker
import sqlalchemy as sa
from alembic import __version__ as __alembic_version__
from alembic.config import Config as AlembicConfig

from simcore_postgres_database.settings import build_url

alembic_version = tuple([int(v) for v in __alembic_version__.split('.')[0:3]])

here = Path( sys.argv[0] if __name__ == "__main__" else __file__ ).parent.resolve()
default_ini = here / 'alembic.ini'
migration_dir = here / 'migration'
discovered_cache = os.path.join( tempfile.mkdtemp(__name__), "discovered_cache.json")

log = logging.getLogger('root')
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
            return if_fails_return
        return safe_func
    return decorate

#@retry(wait=wait_fixed(0.1), stop=stop_after_delay(60))
@safe()
def _ping(url):
    """checks whether database is responsive"""
    engine = sa.create_engine(str(url))
    conn = engine.connect()
    conn.close()
    return True


@safe(if_fails_return=None)
def _get_service_published_port(service_name: str) -> int:
    client = docker.from_env()
    services = [x for x in client.services.list() if service_name in x.name]
    if not services:
        raise RuntimeError("Cannot find published port for service '%s'. Probably services still not up" % service_name)
    service_endpoint = services[0].attrs["Endpoint"]

    if "Ports" not in service_endpoint or not service_endpoint["Ports"]:
        raise RuntimeError("Cannot find published port for service '%s' in endpoint. Probably services still not up" % service_name)

    published_port = service_endpoint["Ports"][0]["PublishedPort"]
    return int(published_port)

def _get_config():
    try:
        with open(discovered_cache) as fh:
            cfg = json.load(fh)

        url = build_url(**cfg)
    except Exception:
        click.echo("Invalid database config, please run discover", err=True)

    config = AlembicConfig(default_ini)
    config.set_main_option('script_location', str(migration_dir))
    config.set_main_option('sqlalchemy.url', str(url))
    return config

def _reset_cache():
    if os.path.exists(discovered_cache):
        os.remove(discovered_cache)
        click.echo("Removed %s" % discovered_cache)


# CLI -----------------------------------------------

@click.group()
def main():
    """ Simplified CLI for database migration with alembic"""
    click.echo("Using alembic {}.{}.{}".format(*alembic_version))

@main.command()
@click.option('--user', '-u', default=os.getenv('POSTGRES_USER'))
@click.option('--password', '-p', default=os.getenv('POSTGRES_PASSWORD'))
@click.option('--host', default=os.getenv('POSTGRES_HOST', 'postgres'))
@click.option('--port', default=os.getenv('POSTGRES_PORT', 5432))
@click.option('--database', default=os.getenv('POSTGRES_DB', 'simcoredb'))
def discover(user, password, host, port, database):
    """ Discovers active databases and stores valid urls"""
    click.echo(f'Discovering database ...')

    # NOTE: Do not add defaults to user, password so we get a chance to ping urls
    # TODO: if multiple candidates online, then query user to select

    try:
        # First guess is via environ variables
        url = build_url(host, port, database, user, password)

        click.echo("Trying url from environs: %s ..." % url)

        if not _ping(url):
            port = _get_service_published_port(host)
            host = "127.0.0.1"
            url = build_url(host, port, database, user, password)

            click.echo("Trying published port in swarm: %s ..." % url)
            if port is None or not _ping(url):
                raise RuntimeError()

        click.secho(f"{url} is online",blink=True, bold=True)
        dumps = json.dumps({
            'user':user,
            'password':password,
            'host':host,
            'port':port,
            'database':database
            }, sort_keys=True, indent=4)

        with open(discovered_cache, 'w') as fh:
            fh.write(dumps)
        click.echo(f"Saved config: {dumps}")


    except Exception as err:
        _reset_cache()
        click.echo("Nothing found. {}".format(err), err=True)
        click.secho("Sorry, database not found !!", blink=True,
            bold=True, fg="red")

@main.command()
@click.option('-m', 'message')
def review(message):
    """Auto-generates a new revison

        alembic revision --autogenerate -m "first tables"
    """
    click.echo('Auto-generates revision based on changes ')

    config = _get_config()
    alembic.command.revision(config, message,
        autogenerate=True, sql=False,
        head='head', splice=False, branch_label=None, version_path=None,
        rev_id=None)

@main.command()
@click.argument('revision', default='head')
def upgrade(revision):
    """Upgrades target database to a given revision"""
    click.echo(f'Upgrading database to {revision} ...')
    config = _get_config()
    alembic.command.upgrade(config, revision, sql=False, tag=None)

@main.command()
def clean():
    """ Resets discover cache """
    _reset_cache()

if __name__ == '__main__':
    main()
