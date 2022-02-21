import logging
import os
from pprint import pformat
from typing import Callable, Optional, Type

import typer
from pydantic import SecretStr, ValidationError
from pydantic.env_settings import BaseSettings

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
    for field in settings_obj.__fields__.values():
        exclude_unset = pydantic_export_options.get("exclude_unset", False)
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


def create_settings_command(
    settings_cls: Type[BaseCustomSettings], logger: Optional[logging.Logger] = None
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
        pydantic_export_options = {"exclude_unset": exclude_unset}

        if as_json_schema:
            typer.echo(settings_cls.schema_json(indent=0 if compact else 2))
            return

        try:
            if show_secrets:
                settings_cls.Config.json_encoders[
                    SecretStr
                ] = lambda v: v.get_secret_value()
            else:
                settings_cls.Config.json_encoders.pop(SecretStr, None)

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
