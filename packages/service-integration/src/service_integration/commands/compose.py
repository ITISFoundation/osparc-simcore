from contextlib import suppress
from pathlib import Path
from typing import Dict, List

import click
import yaml

from ..compose_spec_model import ComposeSpecification
from ..labels_annotations import to_labels
from ..oci_image_spec import LS_LABEL_PREFIX, OCI_LABEL_PREFIX
from ..osparc_config import IoOsparcConfig, ServiceOsparcConfig
from ..osparc_image_specs import create_image_spec


def create_docker_compose_image_spec(
    io_config_path: Path,
    service_config_path: Path,
) -> ComposeSpecification:
    """Creates image compose-spec"""

    config_basedir = io_config_path.parent

    # i/o specs (required)
    io_spec = IoOsparcConfig.from_yaml(io_config_path)

    # service specs (not required)
    service_spec = None
    try:
        # TODO: should include default?
        service_spec = ServiceOsparcConfig.from_yaml(service_config_path)
    except FileNotFoundError:
        pass

    # OCI annotations (not required)
    extra_labels = {}
    try:
        oci_spec = yaml.safe_load(
            (config_basedir / f"{OCI_LABEL_PREFIX}.yml").read_text()
        )
        if not oci_spec:
            raise ValueError("Undefined OCI image spec")

        oci_labels = to_labels(oci_spec, prefix_key=OCI_LABEL_PREFIX)
        extra_labels.update(oci_labels)
    except (FileNotFoundError, ValueError):

        # if not OCI, try label-schema
        with suppress(FileNotFoundError):
            ls_spec = yaml.safe_load(
                (config_basedir / f"{LS_LABEL_PREFIX}.yml").read_text()
            )
            ls_labels = to_labels(ls_spec, prefix_key=LS_LABEL_PREFIX)
            extra_labels.update(ls_labels)

    compose_spec = create_image_spec(io_spec, service_spec, extra_labels=extra_labels)

    return compose_spec


@click.command()
@click.option(
    "-m",
    "--metadata",
    "config_path",
    help="osparc config file or folder",
    type=Path,
    required=False,
    default="metadata.yml",
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
    config_path: Path,
    compose_spec_path: Path,
):
    """create docker image/runtime compose-specs from the osparc config"""

    config_basedir = Path(".osparc")
    metadata_filename = "metadata.yml"

    if config_path.exists():
        if config_path.is_dir():
            config_basedir = config_path
        else:
            config_basedir = config_path.parent
            metadata_filename = config_path.name

    config_filenames: Dict[str, List[Path]] = {}
    if config_basedir.exists():
        for io_config in config_basedir.rglob(metadata_filename):
            config_name = io_config.parent.name
            config_filenames[config_name] = [
                io_config,
            ]

            # find pair (not required)
            service_config = io_config.parent / "runtime.yml"
            if service_config.exists():
                config_filenames[config_name].append(service_config)

    # output
    compose_spec_dict = {}
    for n, config_name in enumerate(config_filenames):
        nth_compose_spec = create_docker_compose_image_spec(
            *config_filenames[config_name]
        ).dict(exclude_unset=True)

        # FIXME: shaky! why first decides ??
        if n == 0:
            compose_spec_dict = nth_compose_spec
        else:
            # appends only services section!
            compose_spec_dict["services"].update(nth_compose_spec["services"])

    compose_spec_path.parent.mkdir(parents=True, exist_ok=True)
    with compose_spec_path.open("wt") as fh:
        yaml.safe_dump(
            compose_spec_dict,
            fh,
            default_flow_style=False,
            sort_keys=False,
        )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
