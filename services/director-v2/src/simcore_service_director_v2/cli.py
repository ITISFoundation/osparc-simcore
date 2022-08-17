import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final
from uuid import UUID

import httpx
import typer
from fastapi import FastAPI
from models_library.projects import NodeIDStr, ProjectID
from pydantic import AnyHttpUrl, parse_obj_as
from servicelib.fastapi.long_running_tasks.client import ClientConfiguration
from settings_library.utils_cli import create_settings_command
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random_exponential

from .core.settings import AppSettings
from .meta import PROJECT_NAME
from .models.schemas.dynamic_services import DynamicSidecarNames
from .modules import db
from .modules.db.repositories.projects import ProjectsRepository
from .modules.director_v0 import DirectorV0Client
from .modules.dynamic_sidecar import api_client
from .modules.dynamic_sidecar.scheduler.events_utils import (
    fetch_repo_outside_of_request,
)
from .modules.projects_networks import requires_dynamic_sidecar

DEFAULT_NODE_SAVE_RETRY: Final[int] = 3

main = typer.Typer(name=PROJECT_NAME)

log = logging.getLogger(__name__)
main.command()(create_settings_command(settings_cls=AppSettings, logger=log))


@asynccontextmanager
async def _initialized_app(settings: AppSettings) -> AsyncIterator[FastAPI]:
    # Initialize minimal required components for the application:
    # - Database
    # - DynamicSidecarClient
    # - DirectorV0Client
    # - long running client configuration

    app = FastAPI()
    app.state.settings = settings
    try:
        await db.events.connect_to_db(app, settings.POSTGRES)
        await api_client.setup(app)

        DirectorV0Client.create(
            app,
            client=httpx.AsyncClient(
                base_url=settings.DIRECTOR_V0.endpoint,
                timeout=app.state.settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
            ),
        )

        app.state.long_running_client_configuration = ClientConfiguration(
            router_prefix="", default_timeout=15
        )

        yield app

    finally:
        await db.events.close_db_connection(app)
        await api_client.shutdown(app)
        client = DirectorV0Client.instance(app).client
        await client.aclose()


def _get_dynamic_sidecar_endpoint(
    settings: AppSettings, node_id: NodeIDStr
) -> AnyHttpUrl:
    dynamic_sidecar_names = DynamicSidecarNames.make(UUID(node_id))
    hostname = dynamic_sidecar_names.service_name_dynamic_sidecar
    port = settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_PORT
    return parse_obj_as(AnyHttpUrl, f"http://{hostname}:{port}")


@main.command()
def project_save_state(
    project_id: ProjectID, retry_save: int = DEFAULT_NODE_SAVE_RETRY
):
    """
    Saves the state of all dy-sidecars in a project.
    In case of error while saving the state of an individual node,
    it will retry to save.
    """

    async def _run() -> None:
        settings = AppSettings.create_from_envs()
        async with _initialized_app(settings) as app:
            projects_repository: ProjectsRepository = fetch_repo_outside_of_request(
                app, ProjectsRepository
            )
            project_at_db = await projects_repository.get_project(project_id)

            typer.echo(
                f"Saving project '{project_at_db.uuid}' - '{project_at_db.name}'"
            )

            dynamic_sidecar_client = api_client.get_dynamic_sidecar_client(app)
            for node_uuid, node_content in project_at_db.workbench.items():
                # onl dynamic-sidecars are used
                if not await requires_dynamic_sidecar(
                    service_key=node_content.key,
                    service_version=node_content.version,
                    director_v0_client=DirectorV0Client.instance(app),
                ):
                    continue

                typer.echo(f"Saving state for {node_uuid} {node_content.label}")

                async for attempt in AsyncRetrying(
                    wait=wait_random_exponential(),
                    stop=stop_after_attempt(retry_save),
                    reraise=True,
                ):
                    with attempt:
                        typer.echo(
                            f"Attempting to save {node_uuid} {node_content.label}"
                        )
                        await dynamic_sidecar_client.save_service_state(
                            _get_dynamic_sidecar_endpoint(settings, node_uuid)
                        )

        typer.echo("Save complete")

    asyncio.run(_run())
