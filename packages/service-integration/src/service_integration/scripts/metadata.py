from pathlib import Path

import click
import yaml
from models_library.services import ServiceDockerData


@click.command()
@click.argument(
    "version_flavour",
    default="version",
    type=click.Choice(["integration_version", "version", "semantic_version"]),
)
@click.option(
    "--increase",
    type=click.Choice(["major", "minor", "patch"]),
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
def bump_version(version_flavour, increase, metadata_file_path):
    """ Increases version in metadata """
    with open(metadata_file_path, "wt") as fh:
        metadata = ServiceDockerData(**yaml.safe_load(fh))

    version_str = getattr(metadata, version_flavour)
    # TODO: parse
    version = version_str.split(".")
    # operation
    version[["major", "minor", "patch"].index(increase)] += 1
    # TODO: format
    version_str = ".".join(version)
    setattr(metadata, version_flavour, version_str)

    metadata_file_path.write_text(yaml.safe_dump(metadata.dict()))
