import json
from contextlib import suppress
from pathlib import Path
from typing import Dict

import click
import yaml
from pydantic import ValidationError
from pydantic.main import BaseModel

from ..compose_spec_model import ComposeSpecification
from ..labels_annotations import to_labels
from ..models import ComposeSpecDict
from ..oci_image_spec import LS_LABEL_PREFIX, OCI_LABEL_PREFIX
from ..osparc_config import IOSpecification, ServiceSpecification
from ..osparc_image_specs import create_image_spec


def create_docker_compose_image_spec(
    compose_spec_path, io_specs_path, service_specs_path
):
    click.echo(f"Creating docker-compose build  -> {compose_spec_path}")

    # specs -> labels

    # i/o specs (required)
    io_spec = IOSpecification.from_yaml(io_specs_path)

    # service specs (not required)
    service_spec = None
    try:
        # TODO: should include default?
        service_spec = ServiceSpecification.from_yaml(service_specs_path)
    except FileNotFoundError:
        pass

    # OCI annotations (not required)
    extra_labels = {}
    try:
        oci_spec = yaml.safe_load(
            (io_specs_path.parent / f"{OCI_LABEL_PREFIX}.yml").read_text()
        )
        if not oci_spec:
            raise ValueError("Undefined OCI image spec")

        oci_labels = to_labels(oci_spec, prefix_key=OCI_LABEL_PREFIX)
        extra_labels.update(oci_labels)
    except (FileNotFoundError, ValueError):

        # if not OCI, try label-schema
        with suppress(FileNotFoundError):
            ls_spec = yaml.safe_load(
                (io_specs_path.parent / f"{LS_LABEL_PREFIX}.yml").read_text()
            )
            ls_labels = to_labels(ls_spec, prefix_key=LS_LABEL_PREFIX)
            extra_labels.update(ls_labels)

    compose_spec = create_image_spec(io_spec, service_spec, extra_labels=extra_labels)

    with compose_spec_path.open("wt") as fh:
        yaml.safe_dump(
            compose_spec.dict(exclude_unset=True),
            fh,
            default_flow_style=False,
            sort_keys=False,
        )

    click.echo("Compose-spec completed")


def create_osparc_specs(
    compose_spec_path: Path,
    io_specs_path: Path = Path("metadata.yml"),
    service_specs_path: Path = Path("simcore.service.yml"),
):
    """Creates io and service specs out of existing compose-spec"""

    click.echo(f"Creating osparc config files from {compose_spec_path}")

    compose_spec = ComposeSpecification.parse_obj(
        yaml.safe_load(compose_spec_path.read_text())
    )

    if compose_spec.services:

        def _save(filename: Path, model: BaseModel):
            with filename.open("wt") as fh:
                data = json.loads(
                    model.json(exclude_unset=True, by_alias=True, exclude_none=True)
                )
                yaml.safe_dump(data, fh, sort_keys=False)

        for service_name in compose_spec.services:
            try:
                labels = compose_spec.services[service_name].build.labels
                if labels:
                    if isinstance(labels, list):
                        labels: Dict[str, str] = dict(
                            item.strip().split("=") for item in labels
                        )
                    assert isinstance(labels.__root__, dict)
                    labels = labels.__root__

                io_spec = IOSpecification.from_labels_annotations(labels)

                _save(
                    io_specs_path.with_name(f"{io_specs_path.stem}-{service_name}.yml"),
                    io_spec,
                )

                service_spec = ServiceSpecification.from_labels_annotations(labels)
                _save(
                    service_specs_path.with_name(
                        f"{service_specs_path.stem}-{service_name}.yml"
                    ),
                    service_spec,
                )

            except (AttributeError, ValidationError, TypeError) as err:
                click.echo(
                    f"WARNING: failure producing specs for {service_name}: {err}"
                )

        click.echo("osparc config files created")


def _tmp(compose_spec_path, io_spec, service_name, compose_labels, io_specs_path):
    def load_compose_spec(compose_file: Path) -> ComposeSpecDict:
        # TODO: auto-generate minimal: catch FileNotFoundError and deduce minimal from model
        with compose_file.open() as fp:
            # TODO: validate with docker-compose config?
            return yaml.safe_load(fp)

    def update_compose_labels(
        compose_spec: ComposeSpecDict, labels: Dict[str, str], service_name: str
    ) -> bool:
        current_labels = compose_spec["services"][service_name]["build"]["labels"]
        updated_labels = {
            key: current_labels[key] for key in sorted(current_labels.keys())
        }

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

    # load if exists
    if compose_spec_path.exists():
        compose_spec = load_compose_spec(compose_spec_path)

    compose_spec.setdefault("services", {io_spec.name: {"build": {"labels": {}}}})

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


####### TMP -----


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
@click.option("--revert/--no-revert", default=False)
def main(
    compose_spec_path: Path,
    io_specs_path: Path,
    service_specs_path: Path,
    revert: bool = False,
):
    """Updates or creates a docker-compose file with json files in a path"""

    if revert:
        create_osparc_specs(compose_spec_path, io_specs_path, service_specs_path)
        return

    create_docker_compose_image_spec(
        compose_spec_path, io_specs_path, service_specs_path
    )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
