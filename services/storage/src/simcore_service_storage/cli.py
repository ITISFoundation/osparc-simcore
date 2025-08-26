import logging
import os

import typer
from settings_library.postgres import PostgresSettings
from settings_library.s3 import S3Settings
from settings_library.utils_cli import (
    create_settings_command,
    create_version_callback,
    print_as_envfile,
)

from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR

_logger = logging.getLogger(__name__)

# NOTE: 'main' variable is referred in the setup's entrypoint!
main = typer.Typer(name=PROJECT_NAME)

main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)
main.callback()(create_version_callback(__version__))


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled. Use instead")
    typer.secho(
        f"$ uvicorn --factory {PROJECT_NAME}.main:app_factory",
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
        STORAGE_POSTGRES=os.environ.get(
            "STORAGE_POSTGRES",
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
        STORAGE_S3=os.environ.get(  # nosec
            "STORAGE_S3",
            S3Settings.create_from_envs(
                S3_BUCKET_NAME=os.environ.get("S3_BUCKET", "replace-with-s3-bucket"),
                S3_ACCESS_KEY=os.environ.get(
                    "S3_ACCESS_KEY", "replace-with-s3-access-key"
                ),
                S3_SECRET_KEY=os.environ.get(
                    "S3_SECRET_KEY", "replace-with-s3-secret-key"
                ),
                S3_ENDPOINT=os.environ.get(
                    "S3_ENDPOINT", "https://s3.replace-with-s3-endpoint"
                ),
                S3_REGION=os.environ.get("S3_REGION", "replace-with-s3-region"),
            ),
        ),
    )

    print_as_envfile(
        settings,
        compact=False,
        verbose=True,
        show_secrets=True,
        exclude_unset=minimal,
    )
