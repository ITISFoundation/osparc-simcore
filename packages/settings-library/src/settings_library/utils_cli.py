import logging
import os
from pprint import pformat
from typing import Callable, Optional, Type

import typer
from pydantic import ValidationError
from pydantic.env_settings import BaseSettings
from pydantic.main import BaseModel

from ._constants import HEADER_STR
from .base import BaseCustomSettings


def print_as_envfile(settings_obj, *, compact, verbose):
    for name in settings_obj.__fields__:
        value = getattr(settings_obj, name)

        if isinstance(value, BaseSettings):
            if compact:
                value = f"'{value.json()}'"  # flat
            else:
                if verbose:
                    typer.echo(f"\n# --- {name} --- ")
                print_as_envfile(value, compact=False, verbose=verbose)
                continue

        if verbose:
            field_info = settings_obj.__fields__[name].field_info
            if field_info.description:
                typer.echo(f"# {field_info.description}")

        typer.echo(f"{name}={value}")


def print_as_json(settings_obj, *, compact=False):
    typer.echo(settings_obj.json(indent=None if compact else 2))


def inject_fake_defaults_fields(model_cls: Type[BaseModel]):
    # copy
    # fake if not default. fake can be determined by schema and faker

    raise NotImplementedError


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
        fake_missing_envs: bool = typer.Option(
            False, help="Adds fake value if required field is not captured in the envs"
        ),
    ):
        """Resolves settings (i.e. parses envs) and echoes them in different formats"""

        if as_json_schema:
            typer.echo(settings_cls.schema_json(indent=0 if compact else 2))
            return

        try:
            settings_obj = settings_cls.create_from_envs()

        except ValidationError as err:
            settings_schema = settings_cls.schema_json(indent=2)

            if fake_missing_envs:
                # take schema
                # create isolated environ? subprocess??
                # add missing variable reported in Validationerror using schema info
                # transfer back json instance
                # create settings_obj using constructor or
                import pdb

                pdb.set_trace()
                raise NotImplementedError()

            assert logger is not None  # nosec
            logger.error(
                "Invalid application settings. Typically an environment variable is missing or mistyped :\n%s",
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
            print_as_json(settings_obj, compact=compact)
        else:
            print_as_envfile(settings_obj, compact=compact, verbose=verbose)

    return settings
