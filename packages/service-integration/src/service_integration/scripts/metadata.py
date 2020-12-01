from pathlib import Path

import click
import yaml
from click.decorators import version_option
from models_library.services import ServiceDockerData
from pkg_resources import parse_version
from service_integration import meta

TARGET_VERSION_CHOICES = ["integration-version", "version"]
UPGRADE_TAGS = ["major", "minor", "patch"]


@click.command()
def bump_version_string(current_version: str, bump: str) -> str:
    """ BUMP means to increment the version number to a new, unique value """
    version = parse_version(current_version)

    # CAN ONLY bump releases not pre/post/dev releases
    if version.is_devrelease or version.is_postrelease or version.is_prerelease:
        raise NotImplementedError("Can only bump released versions")

    major, minor, patch = version.major, version.minor, version.patch
    if bump == "major":
        new_version = f"{major+1}.0.0"
    elif bump == "minor":
        new_version = f"{major}.{minor+1}.0"
    else:
        new_version = f"{major}.{minor}.{patch+1}"
    return new_version


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
    """ Increases version in metadata """

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
            metadata.dict(exclude_none=True, exclude_unset=True, exclude_defaults=True)
        )
    )
    click.echo(f"{target_version.title()} bumped: {current_version} → {new_version}")
