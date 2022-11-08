from collections import OrderedDict
from enum import Enum
from pathlib import Path

import rich
import typer
import yaml
from models_library.services import ServiceDockerData

from ..versioning import bump_version_string
from ..yaml_utils import ordered_safe_dump, ordered_safe_load


class TargetVersionChoices(str, Enum):
    INTEGRATION_VERSION = "integration-version"
    SEMANTIC_VERSION = "version"


class UpgradeTags(str, Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def bump_version(
    target_version: TargetVersionChoices = typer.Argument(
        TargetVersionChoices.SEMANTIC_VERSION
    ),
    upgrade: UpgradeTags = typer.Option(..., case_sensitive=False),
    metadata_file: Path = typer.Option(
        "metadata/metadata.yml",
        help="The metadata yaml file",
    ),
):
    """Bumps target version in metadata  (legacy)"""
    # load
    raw_data: OrderedDict = ordered_safe_load(metadata_file.read_text())

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
    metadata_file.write_text(text)
    rich.print(f"{target_version.title()} bumped: {current_version} → {new_version}")


def get_version(
    target_version: TargetVersionChoices = typer.Argument(
        TargetVersionChoices.SEMANTIC_VERSION
    ),
    metadata_file: Path = typer.Option(
        ".osparc/metadata.yml",
        help="The metadata yaml file",
    ),
):
    """Prints to output requested version (legacy)"""

    # parse and validate
    metadata = ServiceDockerData(**yaml.safe_load(metadata_file.read_text()))

    attrname = target_version.replace("-", "_")
    current_version: str = getattr(metadata, attrname)

    # MUST have no new line so that we can produce a VERSION file with no extra new-line
    # VERSION: $(METADATA)
    #    @osparc-service-integrator get-version --metadata-file $< > $@
    rich.print(current_version, end="")
