import json
import logging
from copy import deepcopy

import click
import sqlalchemy as sa

import docker
from simcore_postgres_database.settings import DSN, db_config, sqlalchemy_url

log = logging.getLogger(__name__)


#@retry(wait=wait_fixed(0.1), stop=stop_after_delay(60))
def ping(url):
    """checks whether database is responsive"""
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except Exception:
        log.error("Something went south ...")
        return False
    return True


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
    """ Discovers active databases """
    click.echo('Discovering database ...')

    cfg = deepcopy(db_config)

    url = DSN.format(**cfg)
    if not ping(url):
        log.error("%s does not respond", url)
        log.info("Discovering host '%s' in swarm ...", cfg['host'])
        try:
            service_name = cfg['host']
            cfg['port'] = get_service_published_port(service_name)
        except RuntimeError:
            log.exception("Probably service does not")
        else:
            cfg['host'] = "127.0.0.1"
            url = DSN.format(**cfg)
            if not ping(url):
                log.error("%s does not respond", url)
            else:
                click.echo(f"{url} responded")

    print( json.dumps(cfg, sort_keys=True, indent=4) )


@cli.command()
def revision():
    """Auto-generates a new revison """
    click.echo('Auto-generates revision based on changes ')


@cli.command()
def upgrade():
    """Upgrades target database to a given revision"""
    click.echo('Upgrading database')



if __name__ == '__main__':
    cli()
