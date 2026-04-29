"""ruff noqa: FBT001, FBT002, FBT003, ARG001"""

# ruff: noqa: FBT001, FBT002, FBT003, ARG001
# pylint: disable=unused-argument
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pprint import pformat
from typing import Any

import rich
import typer
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from pydantic import RootModel, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import to_jsonable_python
from pydantic_settings import BaseSettings

from ._constants import HEADER_STR
from .base import BaseCustomSettings


@dataclass(frozen=True)
class _RenderContext:
    compact: bool
    verbose: bool
    show_secrets: bool
    pydantic_export_options: dict[str, Any]


# A renderer emits the env-file line(s) for a single field and returns True
# when it has handled the value; otherwise the next renderer is tried.
_FieldRenderer = Callable[[str, Any, FieldInfo, _RenderContext], bool]

_FIELD_RENDERERS: list[_FieldRenderer] = []


def _register_field_renderer(fn: _FieldRenderer) -> _FieldRenderer:
    _FIELD_RENDERERS.append(fn)
    return fn


def _dump_with_secrets_as_json(value: Any, ctx: _RenderContext) -> str:
    return json_dumps(
        model_dump_with_secrets(
            value,
            show_secrets=ctx.show_secrets,
            **ctx.pydantic_export_options,
        )
    )


@_register_field_renderer
def _render_base_settings(name: str, value: Any, field: FieldInfo, ctx: _RenderContext) -> bool:
    if not isinstance(value, BaseSettings):
        return False
    if ctx.compact:
        # flat, wrap in single quotes so bash preserves double quotes
        typer.echo(f"{name}='{_dump_with_secrets_as_json(value, ctx)}'")
        return True
    if ctx.verbose:
        typer.echo(f"\n# --- {name} --- ")
    print_as_envfile(
        value,
        compact=False,
        verbose=ctx.verbose,
        show_secrets=ctx.show_secrets,
        **ctx.pydantic_export_options,
    )
    return True


@_register_field_renderer
def _render_root_model(name: str, value: Any, field: FieldInfo, ctx: _RenderContext) -> bool:
    if not isinstance(value, RootModel):
        return False
    # Serialize as JSON so it round-trips through env vars back into the RootModel
    # and honors the same export options used for other Pydantic settings.
    typer.echo(f"{name}='{_dump_with_secrets_as_json(value, ctx)}'")
    return True


@_register_field_renderer
def _render_collection(name: str, value: Any, field: FieldInfo, ctx: _RenderContext) -> bool:
    if not isinstance(value, dict | list):
        return False
    # Serialize complex objects as JSON to ensure they can be parsed correctly.
    # Wrap in single quotes so bash preserves the double quotes when sourcing.
    typer.echo(f"{name}='{json_dumps(value)}'")
    return True


def _render_default(name: str, value: Any, field: FieldInfo, ctx: _RenderContext) -> bool:
    if ctx.show_secrets and hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    if isinstance(value, Enum):
        value = value.value
    typer.echo(f"{name}={value}")
    return True


def _should_skip_field(
    name: str, value: Any, field: FieldInfo, settings_obj: BaseSettings, *, exclude_unset: bool
) -> bool:
    if not exclude_unset or name in settings_obj.model_fields_set:
        return False
    auto_default_from_env = field.json_schema_extra is not None and field.json_schema_extra.get(
        "auto_default_from_env", False
    )
    return not auto_default_from_env or value is None


def print_as_envfile(
    settings_obj,
    *,
    compact: bool,
    verbose: bool,
    show_secrets: bool,
    **pydantic_export_options,
):
    ctx = _RenderContext(
        compact=compact,
        verbose=verbose,
        show_secrets=show_secrets,
        pydantic_export_options=pydantic_export_options,
    )
    exclude_unset = pydantic_export_options.get("exclude_unset", False)

    for name, field in settings_obj.__class__.model_fields.items():
        value = getattr(settings_obj, name)

        if _should_skip_field(name, value, field, settings_obj, exclude_unset=exclude_unset):
            continue

        # Description is printed before the value, but only for non-nested fields
        # (nested BaseSettings handles its own header via the verbose marker).
        if verbose and field.description and not isinstance(value, BaseSettings):
            typer.echo(f"# {field.description}")

        for render in _FIELD_RENDERERS:
            if render(name, value, field, ctx):
                break
        else:
            _render_default(name, value, field, ctx)


def _print_as_json(
    settings_obj,
    *,
    compact: bool = False,
    show_secrets: bool,
    **pydantic_export_options,
):
    typer.echo(
        json_dumps(
            model_dump_with_secrets(settings_obj, show_secrets=show_secrets, **pydantic_export_options),
            indent=None if compact else 2,
        )
    )


def create_settings_command(
    settings_cls: type[BaseCustomSettings],
    logger: logging.Logger | None = None,
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
            "This represents current config (i.e. required+ defaults overridden).",
        ),
    ):
        """Resolves settings and prints envfile"""

        if as_json_schema:
            typer.echo(
                json_dumps(
                    settings_cls.model_json_schema(),
                    default=to_jsonable_python,
                    indent=0 if compact else 2,
                )
            )
            return

        try:
            settings_obj = settings_cls.create_from_envs()

        except ValidationError as err:
            settings_schema = json_dumps(
                settings_cls.model_json_schema(),
                default=to_jsonable_python,
                indent=2,
            )

            assert logger is not None  # nosec
            logger.error(  # noqa: TRY400
                "Invalid settings. Typically this is due to an environment variable missing or misspelled :\n%s",
                "\n".join(
                    [
                        HEADER_STR.format("detail"),
                        str(err),
                        HEADER_STR.format("environment variables"),
                        pformat({k: v for k, v in dict(os.environ).items() if k.upper() == k}),
                        HEADER_STR.format("json-schema"),
                        settings_schema,
                    ]
                ),
                exc_info=False,
            )
            raise

        pydantic_export_options: dict[str, Any] = {"exclude_unset": exclude_unset}

        if as_json:
            _print_as_json(
                settings_obj,
                compact=compact,
                show_secrets=show_secrets,
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
    def _version_callback(value: bool):
        if value:
            rich.print(application_version)
            raise typer.Exit

    def version(
        ctx: typer.Context,
        *,
        version: bool = (  # pylint: disable=unused-argument
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
