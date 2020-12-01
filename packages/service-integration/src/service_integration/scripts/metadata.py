import json
from pathlib import Path

import click
import yaml
from models_library.services import ServiceDockerData

from ..version_utils import bump_version_string

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
    """ Bumps target version in metadata """

    # load and validate metadata
    with open(metadata_file_path, "rt") as fh:
        metadata = ServiceDockerData(**yaml.safe_load(fh))

    # bump
    attrname = target_version.replace("-", "_")
    current_version: str = getattr(metadata, attrname)

    new_version = bump_version_string(current_version, upgrade)

    setattr(metadata, attrname, new_version)

    # dump to file
    metadata_file_path.write_text(
        yaml.safe_dump(
            json.loads(
                metadata.json(
                    exclude_none=True,
                    exclude_unset=True,
                    exclude_defaults=True,
                    by_alias=True,
                )
            )
        )
    )
    click.echo(f"{target_version.title()} bumped: {current_version} → {new_version}")
