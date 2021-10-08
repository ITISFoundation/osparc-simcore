# Allows entrypoint via python -m as well
# pylint: disable=no-name-in-module

import click

from .commands import metadata, run_creator, update_compose_labels
from .meta import __version__


@click.group()
@click.version_option(version=__version__)
def main():
    pass


main.add_command(run_creator.main, "run-creator")
main.add_command(update_compose_labels.main, "update-compose-labels")
main.add_command(metadata.bump_version, "bump-version")
main.add_command(metadata.get_version, "get-version")
