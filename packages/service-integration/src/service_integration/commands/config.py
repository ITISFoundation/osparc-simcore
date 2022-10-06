import json
from pathlib import Path
from typing import Final

import rich
import typer
import yaml
from pydantic import ValidationError
from pydantic.main import BaseModel

from ..compose_spec_model import ComposeSpecification
from ..osparc_config import MetaConfig, RuntimeConfig


def create_osparc_specs(
    compose_spec_path: Path,
    io_specs_path: Path = Path("metadata.yml"),
    service_specs_path: Path = Path("runtime-spec.yml"),
):
    rich.print(f"Creating osparc config files from {compose_spec_path}")

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
            rich.print(f"Creating {output_path} ...", end="")

            with output_path.open("wt") as fh:
                data = json.loads(
                    model.json(exclude_unset=True, by_alias=True, exclude_none=True)
                )
                yaml.safe_dump(data, fh, sort_keys=False)

            rich.print("DONE")

        for service_name in compose_spec.services:
            try:
                labels = compose_spec.services[service_name].build.labels
                if labels:
                    if isinstance(labels, list):
                        labels: dict[str, str] = dict(
                            item.strip().split("=") for item in labels
                        )
                    # TODO: there must be a better way for this ...
                    assert isinstance(labels.__root__, dict)  # nosec
                    labels = labels.__root__

                meta_cfg = MetaConfig.from_labels_annotations(labels)
                _save(
                    service_name,
                    io_specs_path,
                    meta_cfg,
                )

                runtime_cfg = RuntimeConfig.from_labels_annotations(labels)
                _save(
                    service_name,
                    service_specs_path,
                    runtime_cfg,
                )

            except (AttributeError, ValidationError, TypeError) as err:
                rich.print(
                    f"WARNING: failure producing specs for {service_name}: {err}"
                )

        rich.print("osparc config files created")


def main(
    compose_spec_path: Path = typer.Option(
        Path("docker-compose.yml"),
        "-f",
        "--to-spec-file",
        help="Output docker-compose image spec",
    ),
):
    """Creates osparc config from complete docker compose-spec"""
    # TODO: sync defaults among CLI commands
    config_dir = compose_spec_path.parent / ".osparc"
    meta_cfg_path = config_dir / "metadata.yml"
    runtime_cfg_path = config_dir / "runtime.yml"

    meta_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    rich.print(f"Creating {config_dir} from {compose_spec_path} ...")

    create_osparc_specs(compose_spec_path, meta_cfg_path, runtime_cfg_path)
