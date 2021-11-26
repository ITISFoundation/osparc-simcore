from collections import OrderedDict
from pathlib import Path

import click
import yaml
from models_library.services import ServiceDockerData

from ..versioning import bump_version_string
from ..yaml_utils import ordered_safe_dump, ordered_safe_load

TARGET_VERSION_CHOICES = ["integration-version", "version"]
UPGRADE_TAGS = ["major", "minor", "patch"]


@click.command()
@click.argument(
    "target_version",
    default="version",
    type=click.Choice(TARGET_VERSION_CHOICES),
)
@click.option(
    "--upgrade",
    type=click.Choice(UPGRADE_TAGS),
    required=True,
)
@click.option(
    "--metadata-file",
    "metadata_file_path",
    help="The metadata yaml file",
    type=Path,
    required=False,
    default="metadata/metadata.yml",
)
def bump_version(target_version, upgrade, metadata_file_path):
    """Bumps target version in metadata"""
    # load
    raw_data: OrderedDict = ordered_safe_load(metadata_file_path.read_text())

    # parse and validate
    metadata = ServiceDockerData(**raw_data)

    # get + bump + set
    attrname = target_version.replace("-", "_")
    current_version: str = getattr(metadata, attrname)
    raw_data[target_version] = new_version = bump_version_string(
        current_version, upgrade
    )

    # dump to file (preserving order!)
    text = ordered_safe_dump(raw_data)
    metadata_file_path.write_text(text)
    click.echo(f"{target_version.title()} bumped: {current_version} → {new_version}")


@click.command()
@click.argument(
    "target_version",
    default="version",
    type=click.Choice(TARGET_VERSION_CHOICES),
)
@click.option(
    "--metadata-file",
    "metadata_file_path",
    help="The metadata yaml file",
    type=Path,
    required=False,
    default=".osparc/metadata.yml",
)
def get_version(target_version, metadata_file_path):
    """Prints to output requested version"""

    # parse and validate
    metadata = ServiceDockerData(**yaml.safe_load(metadata_file_path.read_text()))

    attrname = target_version.replace("-", "_")
    current_version: str = getattr(metadata, attrname)

    # MUST have no new line so that we can produce a VERSION file with no extra new-line
    # VERSION: $(METADATA)
    #    @osparc-service-integrator get-version --metadata-file $< > $@
    click.echo(current_version, nl=False)
