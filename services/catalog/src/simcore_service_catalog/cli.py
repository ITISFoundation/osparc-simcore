import asyncio
import logging
import os
import urllib.parse
from typing import Any

import httpx
import typer
from models_library.services_metadata_published import ServiceMetaDataPublished
from pydantic import ValidationError
from settings_library.http_client_request import ClientRequestSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_cli import (
    create_settings_command,
    create_version_callback,
    print_as_envfile,
)

from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings, DirectorSettings

_logger = logging.getLogger(__name__)

# NOTE: 'main' variable is referred in the setup's entrypoint!
main = typer.Typer(name=PROJECT_NAME)

main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=_logger))
main.callback()(create_version_callback(__version__))


def _director_base_url(*, director_host: str, director_port: int, director_vtag: str) -> str:
    return f"http://{director_host}:{director_port}/{director_vtag}"


async def _fetch_registry_services(*, base_url: str, timeout_s: float) -> list[dict[str, Any]]:
    endpoint = f"{base_url.rstrip('/')}/services"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as err:
        msg = f"Failed to fetch services from director endpoint {endpoint}: {err}"
        raise RuntimeError(msg) from err

    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list):
        msg = f"Unexpected response payload from director endpoint {endpoint}: {payload!r}"
        raise RuntimeError(msg)

    return [service for service in data if isinstance(service, dict)]


def _find_invalid_services(services: list[dict[str, Any]]) -> list[tuple[dict[str, Any], ValidationError]]:
    invalid_services: list[tuple[dict[str, Any], ValidationError]] = []
    for service in services:
        try:
            ServiceMetaDataPublished.model_validate(service)
        except ValidationError as err:
            invalid_services.append((service, err))
    return invalid_services


async def _delete_registry_service(
    *,
    base_url: str,
    service_key: str,
    service_version: str,
    timeout_s: float,
) -> None:
    encoded_key = urllib.parse.quote(service_key, safe="/")
    encoded_version = urllib.parse.quote(service_version, safe="")
    endpoint = f"{base_url.rstrip('/')}/services/{encoded_key}/{encoded_version}"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.delete(endpoint)
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as err:
        msg = f"Failed deleting service {service_key}:{service_version} via {endpoint}: {err}"
        raise RuntimeError(msg) from err


@main.command()
def run():
    """Runs application"""
    typer.secho("Sorry, this entrypoint is intentionally disabled. Use instead")
    typer.secho(
        "$ uvicorn --factory simcore_service_catalog.main:app_factory",
        fg=typer.colors.BLUE,
    )


@main.command("registry-check")
def registry_check(
    *,
    director_host: str = typer.Option("director", envvar="DIRECTOR_HOST"),
    director_port: int = typer.Option(8080, envvar="DIRECTOR_PORT"),
    director_vtag: str = typer.Option("v0", envvar="DIRECTOR_VTAG"),
    timeout_s: float = typer.Option(20.0, min=1.0),
) -> None:
    """Checks remote registry services (via director) for invalid/incompatible metadata."""
    base_url = _director_base_url(
        director_host=director_host,
        director_port=director_port,
        director_vtag=director_vtag,
    )
    try:
        services = asyncio.run(_fetch_registry_services(base_url=base_url, timeout_s=timeout_s))
    except RuntimeError as err:
        typer.secho(str(err), fg=typer.colors.RED)
        raise typer.Exit(code=1) from err

    invalid_services = _find_invalid_services(services)

    typer.secho(f"Checked {len(services)} services via {base_url}", fg=typer.colors.BLUE)
    if not invalid_services:
        typer.secho("No invalid services detected", fg=typer.colors.GREEN)
        return

    typer.secho(
        f"Detected {len(invalid_services)} invalid services:",
        fg=typer.colors.RED,
    )
    for service_data, error in invalid_services:
        key = service_data.get("key", "<missing-key>")
        version = service_data.get("version", "<missing-version>")
        typer.secho(f"- {key}:{version}", fg=typer.colors.RED)
        typer.echo(error)

    raise typer.Exit(code=1)


@main.command("registry-delete")
def registry_delete(
    *,
    service_key: str = typer.Argument(..., help="Service key, e.g. simcore/services/dynamic/sleeper"),
    service_version: str = typer.Argument(..., help="Service version tag"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    director_host: str = typer.Option("director", envvar="DIRECTOR_HOST"),
    director_port: int = typer.Option(8080, envvar="DIRECTOR_PORT"),
    director_vtag: str = typer.Option("v0", envvar="DIRECTOR_VTAG"),
    timeout_s: float = typer.Option(20.0, min=1.0),
) -> None:
    """Deletes a service image from remote registry via director."""
    if not yes:
        typer.confirm(
            f"Delete '{service_key}:{service_version}' from the remote registry?",
            abort=True,
        )

    base_url = _director_base_url(
        director_host=director_host,
        director_port=director_port,
        director_vtag=director_vtag,
    )
    try:
        asyncio.run(
            _delete_registry_service(
                base_url=base_url,
                service_key=service_key,
                service_version=service_version,
                timeout_s=timeout_s,
            )
        )
    except RuntimeError as err:
        typer.secho(str(err), fg=typer.colors.RED)
        raise typer.Exit(code=1) from err

    typer.secho(f"Deleted {service_key}:{service_version} via {base_url}", fg=typer.colors.GREEN)


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
                POSTGRES_HOST=os.environ.get("POSTGRES_HOST", "replace-with-postgres-host"),
                POSTGRES_USER=os.environ.get("POSTGRES_USER", "replace-with-postgres-user"),
                POSTGRES_DB=os.environ.get("POSTGRES_DB", "replace-with-postgres-db"),
                POSTGRES_PASSWORD=os.environ.get("POSTGRES_PASSWORD", "replace-with-postgres-password"),
            ),
        ),
        CATALOG_RABBITMQ=os.environ.get(
            "CATALOG_RABBITMQ",
            RabbitSettings.create_from_envs(
                RABBIT_HOST=os.environ.get("RABBIT_HOST", "replace-with-rabbit-host"),
                RABBIT_SECURE=os.environ.get("RABBIT_SECURE", "True"),
                RABBIT_USER=os.environ.get("RABBIT_USER", "replace-with-rabbit-user"),
                RABBIT_PASSWORD=os.environ.get("RABBIT_PASSWORD", "replace-with-rabbit-password"),
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
