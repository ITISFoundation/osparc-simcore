# Allows entrypoint via python -m as well

import click

from . import __version__
from .commands import compose, metadata, run_creator


@click.group()
@click.version_option(version=__version__)
def main():
    pass


main.add_command(run_creator.main, "run-creator")
main.add_command(compose.main, "compose")
main.add_command(metadata.bump_version, "bump-version")
main.add_command(metadata.get_version, "get-version")
