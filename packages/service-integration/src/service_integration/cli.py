# Allows entrypoint via python -m as well

import click
from click.core import Context

from . import __version__
from .commands import compose, config, metadata, run_creator
from .context import IntegrationContext

DEFAULTS = IntegrationContext()


@click.group()
@click.pass_context
@click.option(
    "--REGISTRY_NAME",
    "registry_name",
    help="overwrite docker registry",
    type=str,
    default=lambda: DEFAULTS.REGISTRY_NAME,
    show_default=DEFAULTS.REGISTRY_NAME,
)
@click.option(
    "--COMPOSE_VERSION",
    "compose_version",
    help="overwrite docker-compose spec version",
    type=str,
    default=lambda: DEFAULTS.COMPOSE_VERSION,
    show_default=DEFAULTS.COMPOSE_VERSION,
)
@click.version_option(version=__version__)
def main(ctx: Context, registry_name: str, compose_version: str):
    """o2s2parc service integration library"""
    ctx.integration_context = IntegrationContext(
        REGISTRY_NAME=registry_name,
        COMPOSE_VERSION=compose_version,
    )


main.add_command(compose.main, "compose")
main.add_command(config.main, "config")
# previous version
main.add_command(run_creator.main, "run-creator")
main.add_command(metadata.bump_version, "bump-version")
main.add_command(metadata.get_version, "get-version")
