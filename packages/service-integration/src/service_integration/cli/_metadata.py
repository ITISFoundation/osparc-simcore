from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Annotated

import rich
import typer

from ..osparc_config import OSPARC_CONFIG_DIRNAME, MetadataConfig
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
    upgrade: Annotated[UpgradeTags, typer.Option(case_sensitive=False)],
    metadata_file: Annotated[
        Path,
        typer.Option(
            help="The metadata yaml file",
        ),
    ] = Path("metadata/metadata.yml"),
    target_version: Annotated[
        TargetVersionChoices, typer.Argument()
    ] = TargetVersionChoices.SEMANTIC_VERSION,
):
    """Bumps target version in metadata  (legacy)"""
    # load
    raw_data: OrderedDict = ordered_safe_load(metadata_file.read_text())

    # parse and validate
    metadata = MetadataConfig(**raw_data)

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
    target_version: Annotated[
        TargetVersionChoices, typer.Argument()
    ] = TargetVersionChoices.SEMANTIC_VERSION,
    metadata_file: Annotated[
        Path,
        typer.Option(
            help="The metadata yaml file",
        ),
    ] = Path(f"{OSPARC_CONFIG_DIRNAME}/metadata.yml"),
):
    """Prints to output requested version (legacy)"""

    # parse and validate
    metadata = MetadataConfig.from_yaml(metadata_file)

    attrname = target_version.replace("-", "_")
    current_version: str = getattr(metadata, attrname)

    # MUST have no new line so that we can produce a VERSION file with no extra new-line
    # VERSION: $(METADATA)
    #    @simcore-service-integrator get-version --metadata-file $< > $@
    rich.print(current_version, end="")
