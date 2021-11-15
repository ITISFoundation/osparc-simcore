import json
from pathlib import Path
from typing import Dict, Final

import click
import yaml
from pydantic import ValidationError
from pydantic.main import BaseModel

from ..compose_spec_model import ComposeSpecification
from ..osparc_config import IoOsparcConfig, ServiceOsparcConfig


def create_osparc_specs(
    compose_spec_path: Path,
    io_specs_path: Path = Path("metadata.yml"),
    service_specs_path: Path = Path("runtime-spec.yml"),
):
    click.echo(f"Creating osparc config files from {compose_spec_path}")

    compose_spec = ComposeSpecification.parse_obj(
        yaml.safe_load(compose_spec_path.read_text())
    )

    if compose_spec.services:

        has_multiple_services: Final[int] = len(compose_spec.services)

        def _save(service_name: str, filename: Path, model: BaseModel):
            output_path = filename
            if has_multiple_services:
                output_path = filename.parent / service_name / filename.name

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("wt") as fh:
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
                    # TODO: there must be a better way for this ...
                    assert isinstance(labels.__root__, dict)
                    labels = labels.__root__

                io_spec = IoOsparcConfig.from_labels_annotations(labels)
                _save(
                    service_name,
                    io_specs_path,
                    io_spec,
                )

                service_spec = ServiceOsparcConfig.from_labels_annotations(labels)
                _save(
                    service_name,
                    service_specs_path,
                    service_spec,
                )

            except (AttributeError, ValidationError, TypeError) as err:
                click.echo(
                    f"WARNING: failure producing specs for {service_name}: {err}"
                )

        click.echo("osparc config files created")


@click.command()
@click.option(
    "-f",
    "--from-spec-file",
    "compose_spec_path",
    help="docker-compose used to deduce osparc config",
    type=Path,
    required=True,
    default=Path("docker-compose.yml"),
)
def main(
    compose_spec_path: Path,
):
    """Creates osparc config from complete docker compose-spec"""

    # TODO: sync defaults among CLI commands
    config_basedir = compose_spec_path.parent / ".osparc"
    io_specs_path = config_basedir / "metadata.yml"
    service_specs_path = config_basedir / "runtime.yml"

    io_specs_path.parent.mkdir(parents=True, exist_ok=True)
    service_specs_path.parent.mkdir(parents=True, exist_ok=True)

    create_osparc_specs(compose_spec_path, io_specs_path, service_specs_path)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
