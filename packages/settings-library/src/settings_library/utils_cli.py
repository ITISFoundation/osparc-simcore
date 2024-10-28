import json
import logging
import os
from collections.abc import Callable
from enum import Enum
from pprint import pformat
from typing import Any

import rich
import typer
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from pydantic import ValidationError
from pydantic_core import to_jsonable_python
from pydantic_settings import BaseSettings

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

    for name, field in settings_obj.model_fields.items():
        auto_default_from_env = (
            field.json_schema_extra is not None
            and field.json_schema_extra.get("auto_default_from_env", False)
        )

        value = getattr(settings_obj, name)

        if exclude_unset and name not in settings_obj.model_fields_set:
            if not auto_default_from_env:
                continue
            if value is None:
                continue

        if isinstance(value, BaseSettings):
            if compact:
                value = json.dumps(
                    model_dump_with_secrets(
                        value, show_secrets=show_secrets, **pydantic_export_options
                    )
                )  # flat
            else:
                if verbose:
                    typer.echo(f"\n# --- {name} --- ")
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

        if verbose and field.description:
            typer.echo(f"# {field.description}")
        if isinstance(value, Enum):
            value = value.value
        typer.echo(f"{name}={value}")


def print_as_json(
    settings_obj,
    *,
    compact: bool = False,
    show_secrets: bool,
    json_serializer,
    **pydantic_export_options,
):
    typer.echo(
        json_serializer(
            model_dump_with_secrets(
                settings_obj, show_secrets=show_secrets, **pydantic_export_options
            ),
            indent=None if compact else 2,
        )
    )


def create_settings_command(
    settings_cls: type[BaseCustomSettings],
    logger: logging.Logger | None = None,
    json_serializer=json_dumps,
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
            typer.echo(
                json.dumps(
                    settings_cls.model_json_schema(),
                    default=to_jsonable_python,
                    indent=0 if compact else 2,
                )
            )
            return

        try:
            settings_obj = settings_cls.create_from_envs()

        except ValidationError as err:
            settings_schema = json.dumps(
                settings_cls.model_json_schema(),
                default=to_jsonable_python,
                indent=2,
            )

            assert logger is not None  # nosec
            logger.error(  # noqa: TRY400
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

        if as_json:
            print_as_json(
                settings_obj,
                compact=compact,
                show_secrets=show_secrets,
                json_serializer=json_serializer,
                **pydantic_export_options,
            )
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
    def _version_callback(value: bool):  # noqa: FBT001
        if value:
            rich.print(application_version)
            raise typer.Exit

    def version(
        ctx: typer.Context,
        *,
        version: bool = (  # noqa: ARG001 # pylint: disable=unused-argument
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

    return version
