from contextlib import suppress
from pathlib import Path

import click
import yaml

from ..labels_annotations import to_labels
from ..oci_image_spec import LS_LABEL_PREFIX, OCI_LABEL_PREFIX
from ..osparc_config import IOSpecification, ServiceSpecification
from ..osparc_image_specs import create_image_spec


def create_docker_compose_image_spec(
    compose_spec_path: Path,
    io_specs_path: Path,
    service_specs_path: Path,
):
    """Creates image compose-spec"""

    click.echo(f"Creating image-spec -> {compose_spec_path}")

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

    click.echo(f"Created image-spec -> {compose_spec_path}")


@click.command()
@click.option(
    "-m",
    "--metadata",
    "--io-specs",
    "io_specs_path",
    help="osparc config: info and i/o image specs",
    type=Path,
    required=False,
    default=".osparc/metadata.yml",
)
@click.option(
    "-s",
    "--service-specs",
    "service_specs_path",
    help="osparc config: runtime specs",
    type=Path,
    required=False,
    default=".osparc/runtime-spec.yml",
)
@click.option(
    "-f",
    "--to-spec-file",
    "compose_spec_path",
    help="Output docker-compose image spec",
    type=Path,
    required=False,
    default=Path("docker-compose.yml"),
)
def main(
    io_specs_path: Path,
    service_specs_path: Path,
    compose_spec_path: Path,
):
    """create docker image/runtime compose-specs from the osparc config"""
    # TODO: use streams as inputs instead of paths
    compose_spec_path.parent.mkdir(parents=True, exist_ok=True)

    create_docker_compose_image_spec(
        compose_spec_path, io_specs_path, service_specs_path
    )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
