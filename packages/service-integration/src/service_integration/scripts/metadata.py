from pathlib import Path

import click
import yaml
from models_library.services import ServiceDockerData

UPGRADE_TAGS = ["major", "minor", "patch"]


@click.command()
@click.argument(
    "version_flavour",
    default="version",
    type=click.Choice(["integration_version", "version"]),
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
def bump_version(version_flavour, upgrade, metadata_file_path):
    """ Increases version in metadata """

    with open(metadata_file_path, "rt") as fh:
        metadata = ServiceDockerData(**yaml.safe_load(fh))

    version_str: str = getattr(metadata, version_flavour)
    current_version = version_str

    # TODO: implement parser
    release = [int(d) for d in version_str.split(".")]
    release[UPGRADE_TAGS.index(upgrade)] += 1

    # TODO: format
    new_version = ".".join(map(str, release))
    setattr(metadata, version_flavour, new_version)

    click.echo(f"integration version: {current_version} → {new_version}")
    metadata_file_path.write_text(
        yaml.safe_dump(
            metadata.dict(exclude_none=True, exclude_unset=True, exclude_defaults=True)
        )
    )
