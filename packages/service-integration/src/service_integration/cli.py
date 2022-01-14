# Allows entrypoint via python -m as well

import click

from . import __version__
from .commands import compose, config, metadata, run_creator


@click.group()
@click.version_option(version=__version__)
def main():
    """o2s2parc service integration library"""


main.add_command(compose.main, "compose")
main.add_command(config.main, "config")
# previous version
main.add_command(run_creator.main, "run-creator")
main.add_command(metadata.bump_version, "bump-version")
main.add_command(metadata.get_version, "get-version")
