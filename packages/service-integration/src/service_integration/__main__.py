# Allows entrypoint via python -m as well

import click
import service_integration.scripts.metadata as metadata
import service_integration.scripts.run_creator as run_creator
import service_integration.scripts.update_compose_labels as update_compose_labels
from service_integration import __version__


@click.group()
@click.version_option(version=__version__)
@click.option("-v", "--verbose", count=True)
def main(verbose):
    click.echo("Verbosity: %s" % verbose)


main.add_command(run_creator.main, "run-creator")
main.add_command(update_compose_labels.main, "update-compose-labels")
main.add_command(metadata.bump_version, "bump-version")
