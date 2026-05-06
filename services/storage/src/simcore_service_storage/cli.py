import asyncio
import logging
import os

import typer
from asgi_lifespan import LifespanManager
from servicelib.tracing import TracingConfig
from settings_library.postgres import PostgresSettings
from settings_library.s3 import S3Settings
from settings_library.utils_cli import (
    create_settings_command,
    create_version_callback,
    print_as_envfile,
)

from . import _reconciliation as recon
from ._meta import PROJECT_NAME, __version__
from .core.application import create_app
from .core.settings import ApplicationSettings

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR

_logger = logging.getLogger(__name__)

# NOTE: 'main' variable is referred in the setup's entrypoint!
main = typer.Typer(name=PROJECT_NAME)

main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=_logger))
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
    # Nonetheless, if the caller of this CLI has already some **valid** env vars
    # in the environment we want to use them ... and that is why we use `os.environ`.

    settings = ApplicationSettings.create_from_envs(
        STORAGE_POSTGRES=os.environ.get(
            "STORAGE_POSTGRES",
            PostgresSettings.create_from_envs(
                POSTGRES_HOST=os.environ.get("POSTGRES_HOST", "replace-with-postgres-host"),
                POSTGRES_USER=os.environ.get("POSTGRES_USER", "replace-with-postgres-user"),
                POSTGRES_DB=os.environ.get("POSTGRES_DB", "replace-with-postgres-db"),
                POSTGRES_PASSWORD=os.environ.get("POSTGRES_PASSWORD", "replace-with-postgres-password"),
            ),
        ),
        STORAGE_S3=os.environ.get(  # nosec
            "STORAGE_S3",
            S3Settings.create_from_envs(
                S3_BUCKET_NAME=os.environ.get("S3_BUCKET", "replace-with-s3-bucket"),
                S3_ACCESS_KEY=os.environ.get("S3_ACCESS_KEY", "replace-with-s3-access-key"),
                S3_SECRET_KEY=os.environ.get("S3_SECRET_KEY", "replace-with-s3-secret-key"),
                S3_ENDPOINT=os.environ.get("S3_ENDPOINT", "https://s3.replace-with-s3-endpoint"),
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


@main.command()
def reconcile_zombies(
    *,
    s3_to_db: bool = typer.Option(False, "--s3-to-db", help="Wipe orphan <project_id>/ S3 prefixes."),  # noqa: FBT003
    db_to_s3: bool = typer.Option(False, "--db-to-s3", help="Drop file_meta_data rows whose S3 object is missing."),  # noqa: FBT003
    multipart: bool = typer.Option(False, "--multipart", help="Abort abandoned ongoing multipart uploads."),  # noqa: FBT003
    all_passes: bool = typer.Option(False, "--all", help="Run all 3 reconciliation passes."),  # noqa: FBT003
    dry_run: bool = typer.Option(False, "--dry-run", help="Report what would be cleaned without actually deleting."),  # noqa: FBT003
) -> None:
    """One-shot ops command to clean up S3/DB zombies.

    Bypasses the ``STORAGE_CLEANER_RECONCILE_*_ENABLED`` feature flags so the
    operator can act immediately without redeploying. Each requested pass logs
    a structured event per orphan removed; the totals are printed at the end.

    Example::

        $ simcore-service-storage reconcile-zombies --all
        $ simcore-service-storage reconcile-zombies --all --dry-run
        $ simcore-service-storage reconcile-zombies --s3-to-db --multipart
    """
    if all_passes:
        s3_to_db = db_to_s3 = multipart = True

    if not (s3_to_db or db_to_s3 or multipart):
        typer.secho(
            "No pass selected. Use --s3-to-db / --db-to-s3 / --multipart or --all.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=2)

    if dry_run:
        typer.secho("[DRY-RUN] No changes will be made.", fg=typer.colors.CYAN)

    async def _run() -> tuple[int, int, int]:
        settings = ApplicationSettings.create_from_envs()
        tracing_config = TracingConfig.create(tracing_settings=None, service_name="storage-cli")
        app = create_app(settings, tracing_config=tracing_config)

        s3_to_db_count = db_to_s3_count = multipart_count = 0
        async with LifespanManager(app):
            if s3_to_db:
                s3_to_db_count = await recon.reconcile_s3_to_db(app, force=True, dry_run=dry_run)
            if multipart:
                multipart_count = await recon.reconcile_abandoned_multipart_uploads(app, force=True, dry_run=dry_run)
            if db_to_s3:
                db_to_s3_count = await recon.reconcile_db_to_s3(app, force=True, dry_run=dry_run)
        return s3_to_db_count, db_to_s3_count, multipart_count

    s3_n, db_n, mp_n = asyncio.run(_run())
    prefix = "[DRY-RUN] " if dry_run else ""
    typer.secho(f"{prefix}Reconciliation complete:", fg=typer.colors.GREEN)
    typer.echo(f"  S3->DB orphan project prefixes {'found' if dry_run else 'removed'}: {s3_n}")
    typer.echo(f"  DB->S3 dangling fmd rows {'found' if dry_run else 'removed'}:       {db_n}")
    typer.echo(f"  Abandoned multipart uploads {'found' if dry_run else 'aborted'}:    {mp_n}")
