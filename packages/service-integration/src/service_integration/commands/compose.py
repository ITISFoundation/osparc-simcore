import json
from contextlib import suppress
from pathlib import Path
from typing import Dict

import click
import yaml

from ..models import ComposeSpecDict
from ..oci_image_spec import LS_LABEL_PREFIX, OCI_LABEL_PREFIX


def load_compose_spec(compose_file: Path) -> ComposeSpecDict:
    # TODO: auto-generate minimal: catch FileNotFoundError and deduce minimal from model
    with compose_file.open() as fp:
        # TODO: validate with docker-compose config?
        return yaml.safe_load(fp)


def to_labels(
    data: Dict, *, prefix_key: str = "io.simcore", trim_key_head: bool = True
) -> Dict[str, str]:
    # TODO: connect this with models
    # FIXME: null is loaded as 'null' string value? is that correct? json -> None upon deserialization?
    labels = {}
    for key, value in data.items():
        if trim_key_head:
            if isinstance(value, str):
                # TODO: Q&D for ${} variables
                label = value
            else:
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
    "--spec-file",
    "-f",
    "compose_spec_path",
    help="The compose file where labels shall be updated",
    type=Path,
    default=Path("docker-compose.yml"),
)
@click.option(
    "--metadata",
    "--io-specs",
    "io_specs_path",
    help="info and i/o specs",
    type=Path,
    required=False,
    default=".osparc/labels/metadata.yml",
)
@click.option(
    "--service-specs",
    "service_specs_path",
    help="specs for the sidecar",
    type=Path,
    default=".osparc/labels/simcore.service.yml",
)
def main(compose_spec_path: Path, io_specs_path: Path, service_specs_path: Path):
    """Updates or creates a docker-compose file with json files in a path"""

    click.echo("Updating component labels")

    compose_labels = {}

    # specs -> labels

    # i/o specs (required)
    io_spec = yaml.safe_load(io_specs_path.read_text())
    io_labels = to_labels(io_spec, prefix_key="io.simcore", trim_key_head=False)
    compose_labels.update(io_labels)

    # service specs (not required)
    try:
        # TODO: should include default?
        service_spec = yaml.safe_load(service_specs_path.read_text())
        service_labels = to_labels(
            service_spec,
            prefix_key="simcore.service",
        )
        compose_labels.update(service_labels)
    except FileNotFoundError:
        pass

    # OCI annotations (not required)
    try:
        oci_spec = yaml.safe_load(
            (io_specs_path.parent / f"{OCI_LABEL_PREFIX}.yml").read_text()
        )
        if not oci_spec:
            raise ValueError("Undefined OCI image spec")

        oci_labels = to_labels(oci_spec, prefix_key=OCI_LABEL_PREFIX)
        compose_labels.update(oci_labels)
    except (FileNotFoundError, ValueError):

        # if not OCI, try label-schema
        with suppress(FileNotFoundError):
            ls_spec = yaml.safe_load(
                (io_specs_path.parent / f"{LS_LABEL_PREFIX}.yml").read_text()
            )
            ls_labels = to_labels(ls_spec, prefix_key=LS_LABEL_PREFIX)
            compose_labels.update(ls_labels)

    # load if exists
    compose_spec = {"version": "3.7"}
    if compose_spec_path.exists():
        compose_spec = load_compose_spec(compose_spec_path)

    service_name = io_spec["key"].split("/")[-1]
    compose_spec.setdefault("services", {service_name: {"build": {"labels": {}}}})

    # TODO: update_compose_labels should only update section of it
    # TODO: require key ends with service-name, i.e. the one listed in docker-compose.yml::services
    if update_compose_labels(compose_spec, compose_labels, service_name):
        click.echo(
            f"Updating {compose_spec_path} using labels in {io_specs_path}",
        )
        # write the file back
        with compose_spec_path.open("w") as fp:
            yaml.safe_dump(compose_spec, fp, default_flow_style=False, sort_keys=False)
            click.echo("Update completed")
    else:
        click.echo("No update necessary")


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
