import json
from pathlib import Path
from typing import Dict

import click
import yaml


def get_compose_file(compose_file: Path) -> Dict:
    with compose_file.open() as filep:
        return yaml.safe_load(filep)


def get_metadata_file(metadata_file: Path) -> Dict:
    with metadata_file.open() as fp:
        return yaml.safe_load(fp)


def stringify_metadata(metadata: Dict) -> Dict[str, str]:
    jsons = {}
    for key, value in metadata.items():
        jsons[f"io.simcore.{key}"] = json.dumps({key: value})
    return jsons


def update_compose_labels(
    compose_cfg: Dict, metadata: Dict[str, str], service_name: str
) -> bool:
    compose_labels = compose_cfg["services"][service_name]["build"]["labels"]
    changed = False
    for key, value in metadata.items():
        if key in compose_labels:
            if compose_labels[key] == value:
                continue
        compose_labels[key] = value
        changed = True
    return changed


@click.command()
@click.option(
    "--compose",
    "compose_file_path",
    help="The compose file where labels shall be updated",
    type=Path,
    required=True,
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
    compose_cfg = get_compose_file(compose_file_path)
    metadata = get_metadata_file(metadata_file_path)
    json_metadata = stringify_metadata(metadata)

    # TODO: require key ends with service-name, i.e. the one listed in docker-compose.yml::services
    service_name = metadata["key"].split("/")[-1]

    if update_compose_labels(compose_cfg, json_metadata, service_name):
        click.echo(
            "Updating {compose_file_path} using labels in {metadata_file_path}",
        )
        # write the file back
        with compose_file_path.open("w") as fp:
            yaml.safe_dump(compose_cfg, fp, default_flow_style=False)
            click.echo("Update completed")
    else:
        click.echo("No update necessary")


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
