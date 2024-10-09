import json
from pathlib import Path
from typing import Annotated, Final

import rich
import typer
import yaml
from pydantic import BaseModel

from ..compose_spec_model import ComposeSpecification
from ..errors import InvalidLabelsError
from ..osparc_config import (
    OSPARC_CONFIG_COMPOSE_SPEC_NAME,
    OSPARC_CONFIG_DIRNAME,
    OSPARC_CONFIG_METADATA_NAME,
    OSPARC_CONFIG_RUNTIME_NAME,
    DockerComposeOverwriteConfig,
    MetadataConfig,
    RuntimeConfig,
)


def _get_labels_or_raise(build_labels) -> dict[str, str]:
    if isinstance(build_labels, list):
        return dict(item.strip().split("=") for item in build_labels)
    if isinstance(build_labels, dict):
        return build_labels
    if labels__root__ := build_labels.root:
        assert isinstance(labels__root__, dict)  # nosec
        return labels__root__
    raise InvalidLabelsError(build_labels=build_labels)


def _create_config_from_compose_spec(
    compose_spec_path: Path,
    docker_compose_overwrite_path: Path,
    metadata_path: Path,
    service_specs_path: Path,
):
    rich.print(f"Creating osparc config files from {compose_spec_path}")

    compose_spec = ComposeSpecification.model_validate(
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
                data = json.loads(model.model_dump_json(by_alias=True, exclude_none=True))
                yaml.safe_dump(data, fh, sort_keys=False)

            rich.print("DONE")

        for service_name in compose_spec.services:
            try:

                if build_labels := compose_spec.services[
                    service_name
                ].build.labels:  # AttributeError if build is str

                    labels: dict[str, str] = _get_labels_or_raise(build_labels)
                    meta_cfg = MetadataConfig.from_labels_annotations(labels)
                    _save(service_name, metadata_path, meta_cfg)

                    docker_compose_overwrite_cfg = (
                        DockerComposeOverwriteConfig.create_default(
                            service_name=meta_cfg.service_name()
                        )
                    )
                    _save(
                        service_name,
                        docker_compose_overwrite_path,
                        docker_compose_overwrite_cfg,
                    )

                    runtime_cfg = RuntimeConfig.from_labels_annotations(labels)
                    _save(service_name, service_specs_path, runtime_cfg)

            except (  # noqa: PERF203
                AttributeError,
                TypeError,
                ValueError,
            ) as err:
                rich.print(
                    f"WARNING: failure producing specs for {service_name}: {err}"
                )

        rich.print("osparc config files created")


config_app = typer.Typer()


@config_app.command(name="create")
def create_config(
    from_spec_file: Annotated[
        Path,
        typer.Option(
            "-f",
            "--from-spec-file",
            help="docker-compose used to deduce osparc config",
        ),
    ] = Path("docker-compose.yml"),
):
    """Creates osparc configuration folder from a complete docker compose-spec"""
    config_dir = from_spec_file.parent / OSPARC_CONFIG_DIRNAME
    project_cfg_path = config_dir / OSPARC_CONFIG_COMPOSE_SPEC_NAME
    meta_cfg_path = config_dir / OSPARC_CONFIG_METADATA_NAME
    runtime_cfg_path = config_dir / OSPARC_CONFIG_RUNTIME_NAME

    meta_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    rich.print(f"Creating {config_dir} from {from_spec_file} ...")

    _create_config_from_compose_spec(
        from_spec_file, project_cfg_path, meta_cfg_path, runtime_cfg_path
    )


_COOKIECUTTER_GITHUB_URL = "gh:itisfoundation/cookiecutter-osparc-service"


@config_app.command(name="init")
def init_config(
    template: Annotated[
        str, typer.Option(help="Github repo or path to the template")
    ] = _COOKIECUTTER_GITHUB_URL,
    checkout: (
        Annotated[str, typer.Option(help="Branch if different from main")] | None
    ) = None,
):
    """runs cookie-cutter"""
    from cookiecutter.main import cookiecutter  # type: ignore[import-untyped]

    cookiecutter(template, checkout=checkout)
