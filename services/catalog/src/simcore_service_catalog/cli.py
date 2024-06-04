import logging
import os

import typer
from settings_library.http_client_request import ClientRequestSettings
from settings_library.postgres import PostgresSettings
from settings_library.utils_cli import create_settings_command, print_as_envfile

from ._meta import PROJECT_NAME
from .core.settings import ApplicationSettings, DirectorSettings

_logger = logging.getLogger(__name__)

# NOTE: 'main' variable is referred in the setup's entrypoint!
main = typer.Typer(name=PROJECT_NAME)

main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled. Use instead")
    typer.secho(
        "$ uvicorn simcore_service_catalog.main:the_app",
        fg=typer.colors.BLUE,
    )


@main.command()
def echo_dotenv(ctx: typer.Context, *, minimal: bool = True) -> None:
    """Generates and displays a valid environment variables file (also known as dot-envfile)

    Usage:
        $ simcore-service echo-dotenv > .env
        $ cat .env
        $ set -o allexport; source .env; set +o allexport
    """
    assert ctx  # nosec

    # NOTE: we normally DO NOT USE `os.environ` to capture env vars but this is a special case
    # The idea here is to have a command that can generate a **valid** `.env` file that can be used
    # to initialized the app. For that reason we fill required fields of the `ApplicationSettings` with
    # "fake" but valid values (e.g. generating a password or adding tags as `replace-with-api-key).
    # Nonetheless, if the caller of this CLI has already some **valid** env vars in the environment we want to use them ...
    # and that is why we use `os.environ`.

    settings = ApplicationSettings.create_from_envs(
        CATALOG_POSTGRES=os.environ.get(
            "CATALOG_POSTGRES",
            PostgresSettings.create_from_envs(
                POSTGRES_HOST=os.environ.get(
                    "POSTGRES_HOST", "replace-with-postgres-host"
                ),
                POSTGRES_USER=os.environ.get(
                    "POSTGRES_USER", "replace-with-postgres-user"
                ),
                POSTGRES_DB=os.environ.get("POSTGRES_DB", "replace-with-postgres-db"),
                POSTGRES_PASSWORD=os.environ.get(
                    "POSTGRES_PASSWORD", "replace-with-postgres-password"
                ),
            ),
        ),
        CATALOG_DIRECTOR=DirectorSettings.create_from_envs(
            DIRECTOR_HOST=os.environ.get("DIRECTOR_HOST", "fake-director")
        ),
        CATALOG_CLIENT_REQUEST=ClientRequestSettings.create_from_envs(),
    )

    print_as_envfile(
        settings,
        compact=False,
        verbose=True,
        show_secrets=True,
        exclude_unset=minimal,
    )
