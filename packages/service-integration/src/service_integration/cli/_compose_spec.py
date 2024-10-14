import subprocess
from pathlib import Path
from typing import Annotated

import arrow
import rich
import typer
import yaml
from models_library.utils.labels_annotations import to_labels
from rich.console import Console
from yarl import URL

from ..compose_spec_model import ComposeSpecification
from ..errors import UndefinedOciImageSpecError
from ..oci_image_spec import LS_LABEL_PREFIX, OCI_LABEL_PREFIX
from ..osparc_config import (
    OSPARC_CONFIG_DIRNAME,
    DockerComposeOverwriteConfig,
    MetadataConfig,
    RuntimeConfig,
)
from ..osparc_image_specs import create_image_spec
from ..settings import AppSettings

error_console = Console(stderr=True)


def _run_git(*args) -> str:
    """:raises CalledProcessError"""
    return subprocess.run(  # nosec
        ["git", *list(args)],
        capture_output=True,
        encoding="utf8",
        check=True,
    ).stdout.strip()


def _strip_credentials(url: str) -> str:
    if (yarl_url := URL(url)) and yarl_url.is_absolute():
        stripped_url = URL(url).with_user(None).with_password(None)
        return f"{stripped_url}"
    return url


def _run_git_or_empty_string(*args) -> str:
    try:
        return _run_git(*args)
    except FileNotFoundError as err:
        error_console.print(
            "WARNING: Defaulting label to emtpy string",
            "since git is not installed or cannot be executed:",
            err,
        )
    except subprocess.CalledProcessError as err:
        error_console.print(
            "WARNING: Defaulting label to emtpy string",
            "due to:",
            err.stderr,
        )
    return ""


def create_docker_compose_image_spec(
    settings: AppSettings,
    *,
    meta_config_path: Path,
    docker_compose_overwrite_path: Path | None = None,
    service_config_path: Path | None = None,
) -> ComposeSpecification:
    """Creates image compose-spec"""

    config_basedir = meta_config_path.parent

    # REQUIRED
    meta_cfg = MetadataConfig.from_yaml(meta_config_path)

    # REQUIRED
    if docker_compose_overwrite_path:
        docker_compose_overwrite_cfg = DockerComposeOverwriteConfig.from_yaml(
            docker_compose_overwrite_path
        )
    else:
        docker_compose_overwrite_cfg = DockerComposeOverwriteConfig.create_default(
            service_name=meta_cfg.service_name()
        )

    # OPTIONAL
    runtime_cfg = None
    if service_config_path:
        try:
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
            raise UndefinedOciImageSpecError

        oci_labels = to_labels(oci_spec, prefix_key=OCI_LABEL_PREFIX)
        extra_labels.update(oci_labels)
    except (FileNotFoundError, UndefinedOciImageSpecError):
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

    # SEE https://github.com/opencontainers/image-spec/blob/main/annotations.md#pre-defined-annotation-keys
    # Format the datetime object as a string following RFC-3339
    rfc3339_format = arrow.now().format("YYYY-MM-DDTHH:mm:ssZ")
    extra_labels[f"{LS_LABEL_PREFIX}.build-date"] = rfc3339_format
    extra_labels[f"{LS_LABEL_PREFIX}.schema-version"] = "1.0"

    extra_labels[f"{LS_LABEL_PREFIX}.vcs-ref"] = _run_git_or_empty_string(
        "rev-parse", "HEAD"
    )
    extra_labels[f"{LS_LABEL_PREFIX}.vcs-url"] = _strip_credentials(
        _run_git_or_empty_string("config", "--get", "remote.origin.url")
    )

    return create_image_spec(
        settings,
        meta_cfg,
        docker_compose_overwrite_cfg,
        runtime_cfg,
        extra_labels=extra_labels,
    )


def create_compose(
    ctx: typer.Context,
    config_path: Annotated[
        Path,
        typer.Option(
            "-m",
            "--metadata",
            help="osparc config file or folder. "
            "If the latter, it will scan for configs using the glob pattern 'config_path/**/metadata.yml' ",
        ),
    ] = Path(OSPARC_CONFIG_DIRNAME),
    to_spec_file: Annotated[
        Path,
        typer.Option(
            "-f",
            "--to-spec-file",
            help="Output docker-compose image spec",
        ),
    ] = Path("docker-compose.yml"),
):
    """Creates the docker image/runtime compose-spec file from an .osparc config"""

    if not config_path.exists():
        msg = "Invalid path to metadata file or folder"
        raise typer.BadParameter(msg)

    if config_path.is_dir():
        # equivalent to 'basedir/**/metadata.yml'
        basedir = config_path
        config_pattern = "metadata.yml"
    else:
        # equivalent to 'config_path'
        basedir = config_path.parent
        config_pattern = config_path.name

    configs_kwargs_map: dict[str, dict[str, Path]] = {}

    for meta_config in sorted(basedir.rglob(config_pattern)):
        config_name = meta_config.parent.name
        configs_kwargs_map[config_name] = {}

        # load meta REQUIRED
        configs_kwargs_map[config_name]["meta_config_path"] = meta_config

        # others OPTIONAL
        for file_name, arg_name in (
            ("docker-compose.overwrite.yml", "docker_compose_overwrite_path"),
            ("runtime.yml", "service_config_path"),
        ):
            file_path = meta_config.parent / file_name
            if file_path.exists():
                configs_kwargs_map[config_name][arg_name] = file_path

    if not configs_kwargs_map:
        rich.print(f"[warning] No config files were found in '{config_path}'")

    # output
    compose_spec_dict = {}

    assert ctx.parent  # nosec
    settings: AppSettings = ctx.parent.settings  # type: ignore[attr-defined] # pylint:disable=no-member

    for n, config_name in enumerate(configs_kwargs_map):
        nth_compose_spec = create_docker_compose_image_spec(
            settings, **configs_kwargs_map[config_name]
        ).model_dump(exclude_unset=True)

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
    rich.print(f"Created compose specs at '{to_spec_file.resolve()}'")
