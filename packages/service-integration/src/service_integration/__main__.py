# Allows entrypoint via python -m as well

import click
import service_integration.scripts.run_creator as run_creator
import service_integration.scripts.update_compose_labels as update_compose_labels
from service_integration import __version__


@click.group()
@click.version_option(version=__version__)
def main():
    pass


main.add_command(run_creator.main, "run-creator")
main.add_command(update_compose_labels.main, "update-compose-labels")
