import json
from pathlib import Path
from typing import Dict

import click
import yaml

from ..models import ComposeSpecDict


def load_compose_spec(compose_file: Path) -> ComposeSpecDict:
    # TODO: auto-generate minimal: catch FileNotFoundError and deduce minimal from model
    with compose_file.open() as fp:
        # TODO: validate with docker-compose config?
        return yaml.safe_load(fp)


def load_io_specs(metadata_file: Path) -> Dict:
    with metadata_file.open() as fp:
        return yaml.safe_load(fp)
        # TODO: validate using pydantic model


def to_labels(
    data: Dict, *, prefix_key: str = "io.simcore", trim_key_head: bool = False
) -> Dict[str, str]:
    # TODO: connect this with models
    # FIXME: null is loaded as 'null' string value? is that correct? json -> None upon deserialization?
    labels = {}
    for key, value in data.items():
        if trim_key_head:
            label = json.dumps(value, sort_keys=False)
        else:
            label = json.dumps({key: value}, sort_keys=False)

        labels[f"{prefix_key}.{key}"] = label

    return labels


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
    "io_specs_path",
    help="The metadata yaml file",
    type=Path,
    required=False,
    default="metadata/metadata.yml",
)
@click.option("--service-specs", "service_specs_path", type=Path)
def main(compose_file_path: Path, io_specs_path: Path, service_specs_path: Path):
    """Update a docker-compose file with json files in a path

    Usage: python update_compose_labels --c docker-compose.yml -f folder/path

    """

    click.echo("Updating component labels")

    # load if exists
    compose_spec = {}
    if compose_file_path.exists():
        compose_spec = load_compose_spec(compose_file_path)

    # specs
    io_spec = load_io_specs(io_specs_path)
    service_spec = yaml.safe_load(service_specs_path.read_text())

    # specs -> labels
    io_labels = to_labels(io_spec, prefix_key="io.simcore", trim_key_head=False)
    service_labels = to_labels(
        service_spec, prefix_key="simcore.service", trim_key_head=True
    )

    compose_labels = {**io_labels, **service_labels}

    # TODO: require key ends with service-name, i.e. the one listed in docker-compose.yml::services
    service_name = io_spec["key"].split("/")[-1]

    if update_compose_labels(compose_spec, compose_labels, service_name):
        click.echo(
            f"Updating {compose_file_path} using labels in {io_specs_path}",
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
