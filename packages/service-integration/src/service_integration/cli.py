# Allows entrypoint via python -m as well

import click

from .meta import __version__
from .scripts import metadata, run_creator, update_compose_labels


@click.group()
@click.version_option(version=__version__)
@click.option("-v", "--verbose", count=True)
def main(verbose):
    click.echo("Verbosity: %s" % verbose)


main.add_command(run_creator.main, "run-creator")
main.add_command(update_compose_labels.main, "update-compose-labels")
main.add_command(metadata.bump_version, "bump-version")
