from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError, check_output
from typing import Optional

import rich
import typer
import yaml

from ..compose_spec_model import ComposeSpecification
from ..context import IntegrationContext
from ..labels_annotations import to_labels
from ..oci_image_spec import LS_LABEL_PREFIX, OCI_LABEL_PREFIX
from ..osparc_config import DockerComposeOverwriteCfg, MetaConfig, RuntimeConfig
from ..osparc_image_specs import create_image_spec


def _utc_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _command_output(command: str, *, default: Optional[str] = None) -> Optional[str]:
    try:
        return check_output(command, shell=True).decode().strip()
    except CalledProcessError:
        return default


def create_docker_compose_image_spec(
    integration_context: IntegrationContext,
    meta_config_path: Path,
    docker_compose_overwrite_path: Path,
    service_config_path: Path = None,
) -> ComposeSpecification:
    """Creates image compose-spec"""

    config_basedir = meta_config_path.parent

    # required
    meta_cfg = MetaConfig.from_yaml(meta_config_path)

    # required
    docker_compose_overwrite_cfg = DockerComposeOverwriteCfg.from_yaml(
        docker_compose_overwrite_path, service_name=meta_cfg.service_name()
    )

    # optional
    runtime_cfg = None
    if service_config_path:
        try:
            # TODO: should include default?
            runtime_cfg = RuntimeConfig.from_yaml(service_config_path)
        except FileNotFoundError:
            rich.print("No runtime config found (optional), using default.")

    # OCI annotations (optional)
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

        try:
            # if not OCI, try label-schema
            ls_spec = yaml.safe_load(
                (config_basedir / f"{LS_LABEL_PREFIX}.yml").read_text()
            )
            ls_labels = to_labels(ls_spec, prefix_key=LS_LABEL_PREFIX)
            extra_labels.update(ls_labels)
        except FileNotFoundError:
            rich.print(
                "No explicit config for OCI/label-schema found (optional), skipping OCI annotations."
            )
    # add required labels
    extra_labels[f"{LS_LABEL_PREFIX}.build-date"] = _utc_timestamp()
    extra_labels[f"{LS_LABEL_PREFIX}.schema-version"] = "1.0"
    extra_labels[f"{LS_LABEL_PREFIX}.vcs-ref"] = _command_output(
        "git describe --always", default=""
    )
    extra_labels[f"{LS_LABEL_PREFIX}.vcs-url"] = _command_output(
        "git config --get remote.origin.url", default=""
    )

    compose_spec = create_image_spec(
        integration_context,
        meta_cfg,
        docker_compose_overwrite_cfg,
        runtime_cfg,
        extra_labels=extra_labels,
    )

    return compose_spec


def main(
    ctx: typer.Context,
    config_path: Path = typer.Option(
        "metadata.yml",
        "-m",
        "--metadata",
        help="osparc config file or folder",
    ),
    to_spec_file: Path = typer.Option(
        Path("docker-compose.yml"),
        "-f",
        "--to-spec-file",
        help="Output docker-compose image spec",
    ),
):
    """create docker image/runtime compose-specs from an osparc config"""

    basedir = Path(".osparc")
    meta_filename = "metadata.yml"

    # TODO: all these MUST be replaced by osparc_config.ConfigFilesStructure
    if config_path.exists():
        if config_path.is_dir():
            basedir = config_path
        else:
            basedir = config_path.parent
            meta_filename = config_path.name

    config_filenames: dict[str, list[Path]] = {}
    if basedir.exists():
        for meta_cfg in sorted(list(basedir.rglob(meta_filename))):
            config_name = meta_cfg.parent.name
            config_filenames[config_name] = []
            # load meta
            config_filenames[config_name].append(meta_cfg)

            # loads overwrites
            docker_compose_overwrite_path = (
                meta_cfg.parent / "docker-compose.overwrite.yml"
            )
            if docker_compose_overwrite_path.exists():
                config_filenames[config_name].append(docker_compose_overwrite_path)

            # find pair (not required)
            runtime_cfg = meta_cfg.parent / "runtime.yml"
            if runtime_cfg.exists():
                config_filenames[config_name].append(runtime_cfg)

    # output
    compose_spec_dict = {}
    for n, config_name in enumerate(config_filenames):
        nth_compose_spec = create_docker_compose_image_spec(
            ctx.parent.integration_context, *config_filenames[config_name]
        ).dict(exclude_unset=True)

        # FIXME: shaky! why first decides ??
        if n == 0:
            compose_spec_dict = nth_compose_spec
        else:
            # appends only services section!
            compose_spec_dict["services"].update(nth_compose_spec["services"])

    to_spec_file.parent.mkdir(parents=True, exist_ok=True)
    with to_spec_file.open("wt") as fh:
        yaml.safe_dump(
            compose_spec_dict,
            fh,
            default_flow_style=False,
            sort_keys=False,
        )
