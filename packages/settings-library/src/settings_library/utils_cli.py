import logging
import os
from functools import partial
from pprint import pformat
from typing import Any, Callable, Optional

import rich
import typer
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic.env_settings import BaseSettings
from pydantic.json import custom_pydantic_encoder

from ._constants import HEADER_STR
from .base import BaseCustomSettings


def print_as_envfile(
    settings_obj,
    *,
    compact: bool,
    verbose: bool,
    show_secrets: bool,
    **pydantic_export_options,
):
    exclude_unset = pydantic_export_options.get("exclude_unset", False)

    for field in settings_obj.__fields__.values():
        auto_default_from_env = field.field_info.extra.get(
            "auto_default_from_env", False
        )

        value = getattr(settings_obj, field.name)

        if exclude_unset and field.name not in settings_obj.__fields_set__:
            if not auto_default_from_env:
                continue
            if value is None:
                continue

        if isinstance(value, BaseSettings):
            if compact:
                value = f"'{value.json(**pydantic_export_options)}'"  # flat
            else:
                if verbose:
                    typer.echo(f"\n# --- {field.name} --- ")
                print_as_envfile(
                    value,
                    compact=False,
                    verbose=verbose,
                    show_secrets=show_secrets,
                    **pydantic_export_options,
                )
                continue
        elif show_secrets and hasattr(value, "get_secret_value"):
            value = value.get_secret_value()

        if verbose:
            field_info = field.field_info
            if field_info.description:
                typer.echo(f"# {field_info.description}")

        typer.echo(f"{field.name}={value}")


def print_as_json(settings_obj, *, compact=False, **pydantic_export_options):
    typer.echo(
        settings_obj.json(indent=None if compact else 2, **pydantic_export_options)
    )


def create_json_encoder_wo_secrets(model_cls: type[BaseModel]):
    current_encoders = getattr(model_cls.Config, "json_encoders", {})
    encoder = partial(
        custom_pydantic_encoder,
        {
            SecretStr: lambda v: v.get_secret_value(),
            **current_encoders,
        },
    )
    return encoder


def create_settings_command(
    settings_cls: type[BaseCustomSettings], logger: logging.Logger | None = None
) -> Callable:
    """Creates typer command function for settings"""

    assert issubclass(settings_cls, BaseCustomSettings)  # nosec
    assert settings_cls != BaseCustomSettings  # nosec

    if logger is None:
        logger = logging.getLogger(__name__)

    def settings(
        as_json: bool = False,
        as_json_schema: bool = False,
        compact: bool = typer.Option(False, help="Print compact form"),
        verbose: bool = False,
        show_secrets: bool = False,
        exclude_unset: bool = typer.Option(
            False,
            help="displays settings that were explicitly set"
            "This represents current config (i.e. required+ defaults overriden).",
        ),
    ):
        """Resolves settings and prints envfile"""

        if as_json_schema:
            typer.echo(settings_cls.schema_json(indent=0 if compact else 2))
            return

        try:
            settings_obj = settings_cls.create_from_envs()

        except ValidationError as err:
            settings_schema = settings_cls.schema_json(indent=2)

            assert logger is not None  # nosec
            logger.error(
                "Invalid settings. "
                "Typically this is due to an environment variable missing or misspelled :\n%s",
                "\n".join(
                    [
                        HEADER_STR.format("detail"),
                        str(err),
                        HEADER_STR.format("environment variables"),
                        pformat(
                            {
                                k: v
                                for k, v in dict(os.environ).items()
                                if k.upper() == k
                            }
                        ),
                        HEADER_STR.format("json-schema"),
                        settings_schema,
                    ]
                ),
                exc_info=False,
            )
            raise

        pydantic_export_options: dict[str, Any] = {"exclude_unset": exclude_unset}
        if show_secrets:
            # NOTE: this option is for json-only
            pydantic_export_options["encoder"] = create_json_encoder_wo_secrets(
                settings_cls
            )

        if as_json:
            print_as_json(settings_obj, compact=compact, **pydantic_export_options)
        else:
            print_as_envfile(
                settings_obj,
                compact=compact,
                verbose=verbose,
                show_secrets=show_secrets,
                **pydantic_export_options,
            )

    return settings


def create_version_callback(application_version: str) -> Callable:
    def _version_callback(value: bool):
        if value:
            rich.print(application_version)
            raise typer.Exit()

    def version(
        ctx: typer.Context,
        version: Optional[bool] = (
            typer.Option(
                None,
                "--version",
                callback=_version_callback,
                is_eager=True,
            )
        ),
    ):
        """current version"""
        assert ctx  # nosec
        assert version or not version  # nosec

    return version
