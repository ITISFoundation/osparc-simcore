import logging
import os
from pprint import pformat

import typer
from pydantic import ValidationError
from pydantic.env_settings import BaseSettings

from . import application
from .log import setup_logging
from .settings import Settings

# ptsvd cause issues with ProcessPoolExecutor
# SEE: https://github.com/microsoft/ptvsd/issues/1443
if os.environ.get("SC_BOOT_MODE") == "debug-ptvsd":
    import multiprocessing

    multiprocessing.set_start_method("spawn", True)

log = logging.getLogger(__name__)


HEADER = "{:-^50}"


log = logging.getLogger(__name__)
main = typer.Typer(name="osparc-simcore webserver service")


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


@main.command()
def settings(
    as_json: bool = False,
    as_json_schema: bool = False,
    compact: bool = typer.Option(False, help="Print compact form"),
    verbose: bool = False,
):
    """Resolves settings and prints envfile"""

    if as_json_schema:
        typer.echo(Settings.schema_json(indent=0 if compact else 2))
        return

    try:
        settings_obj = Settings.create_from_env()

    except ValidationError as err:
        settings_schema = Settings.schema_json(indent=2)
        log.error(
            "Invalid application settings. Typically an environment variable is missing or mistyped :\n%s",
            "\n".join(
                [
                    HEADER.format("detail"),
                    str(err),
                    HEADER.format("environment variables"),
                    pformat(
                        {k: v for k, v in dict(os.environ).items() if k.upper() == k}
                    ),
                    HEADER.format("json-schema"),
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


@main.command()
def run():
    """Runs application"""
    typer.secho("Resolving settings ...", nl=False)
    settings_obj = Settings.create_from_env()
    typer.secho("DONE", fg=typer.colors.GREEN)

    # service log level
    slow_duration = float(
        os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0)
    )  # TODO: move to settings.py::ApplicationSettings
    setup_logging(level=settings_obj.logging_level, slow_duration=slow_duration)

    typer.secho("Starting app ... ")
    application.run_service(settings_obj)
