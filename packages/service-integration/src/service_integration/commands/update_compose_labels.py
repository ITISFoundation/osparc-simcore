import json
from pathlib import Path
from typing import Dict

import click
import yaml

from ..models import ComposeSpecDict


def get_compose_file(compose_file: Path) -> ComposeSpecDict:
    # TODO: auto-generate minimal: catch FileNotFoundError and deduce minimal from model
    with compose_file.open() as fp:
        # TODO: validate with docker-compose config?
        return yaml.safe_load(fp)


def get_metadata_file(metadata_file: Path) -> Dict:
    with metadata_file.open() as fp:
        return yaml.safe_load(fp)
        # TODO: validate using pydantic model


def stringify_metadata(metadata: Dict) -> Dict[str, str]:
    jsons = {}
    for key, value in metadata.items():
        # TODO: connect this with models
        jsons[f"io.simcore.{key}"] = json.dumps({key: value}, sort_keys=False)
    return jsons


def update_compose_labels(
    compose_spec: ComposeSpecDict, labels: Dict[str, str], service_name: str
) -> bool:
    current_labels = compose_spec["services"][service_name]["build"]["labels"]
    updated_labels = {key: current_labels[key] for key in sorted(current_labels.keys())}

    changed: bool = list(current_labels.keys()) != list(updated_labels.keys())
    for key, value in labels.items():
        if key in updated_labels:
            if updated_labels[key] == value:
                continue
        updated_labels[key] = value
        changed = True

    if changed:
        compose_spec["services"][service_name]["build"]["labels"] = updated_labels

    return changed


@click.command()
@click.option(
    "--compose",
    "compose_file_path",
    help="The compose file where labels shall be updated",
    type=Path,
    default=Path("docker-compose-meta.yml"),
)
@click.option(
    "--metadata",
    "--metadata-file",
    "metadata_file_path",
    help="The metadata yaml file",
    type=Path,
    required=False,
    default="metadata/metadata.yml",
)
def main(compose_file_path: Path, metadata_file_path: Path):
    """Update a docker-compose file with json files in a path

    Usage: python update_compose_labels --c docker-compose.yml -f folder/path

    """

    click.echo("Updating component labels")
    # get available jsons
    compose_spec = get_compose_file(compose_file_path)
    metadata = get_metadata_file(metadata_file_path)
    json_metadata = stringify_metadata(metadata)

    # TODO: require key ends with service-name, i.e. the one listed in docker-compose.yml::services
    service_name = metadata["key"].split("/")[-1]

    if update_compose_labels(compose_spec, json_metadata, service_name):
        click.echo(
            f"Updating {compose_file_path} using labels in {metadata_file_path}",
        )
        # write the file back
        with compose_file_path.open("w") as fp:
            yaml.safe_dump(compose_spec, fp, default_flow_style=False, sort_keys=False)
            click.echo("Update completed")
    else:
        click.echo("No update necessary")


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
