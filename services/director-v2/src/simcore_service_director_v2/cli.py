import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final
from uuid import UUID

import typer
from fastapi import FastAPI
from models_library.projects import NodeIDStr, ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import AnyHttpUrl, parse_obj_as
from settings_library.utils_cli import create_settings_command
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random_exponential

from .core.application import create_base_app
from .core.settings import AppSettings
from .meta import PROJECT_NAME
from .models.schemas.dynamic_services import DynamicSidecarNames
from .modules import db, director_v0, dynamic_sidecar
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
async def _initialized_app() -> AsyncIterator[FastAPI]:
    app = create_base_app()
    settings: AppSettings = app.state.settings

    # Initialize minimal required components for the application
    db.setup(app, settings.POSTGRES)
    dynamic_sidecar.setup(app)
    director_v0.setup(app, settings.DIRECTOR_V0)

    await app.router.startup()
    yield app
    await app.router.shutdown()


def _get_dynamic_sidecar_endpoint(
    settings: AppSettings, node_id: NodeIDStr
) -> AnyHttpUrl:
    dynamic_sidecar_names = DynamicSidecarNames.make(UUID(node_id))
    hostname = dynamic_sidecar_names.service_name_dynamic_sidecar
    port = settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_PORT
    return parse_obj_as(AnyHttpUrl, f"http://{hostname}:{port}")  # NOSONAR


async def _save_node_state(
    app,
    dynamic_sidecar_client: api_client.DynamicSidecarClient,
    retry_save: int,
    node_uuid: NodeIDStr,
    label: str = "",
) -> None:
    typer.echo(f"Saving state for {node_uuid} {label}")
    async for attempt in AsyncRetrying(
        wait=wait_random_exponential(),
        stop=stop_after_attempt(retry_save),
        reraise=True,
    ):
        with attempt:
            typer.echo(f"Attempting to save {node_uuid} {label}")
            await dynamic_sidecar_client.save_service_state(
                _get_dynamic_sidecar_endpoint(app.state.settings, node_uuid)
            )


async def _async_project_save_state(project_id: ProjectID, retry_save: int) -> None:
    async with _initialized_app() as app:
        projects_repository: ProjectsRepository = fetch_repo_outside_of_request(
            app, ProjectsRepository
        )
        project_at_db = await projects_repository.get_project(project_id)

        typer.echo(f"Saving project '{project_at_db.uuid}' - '{project_at_db.name}'")

        dynamic_sidecar_client = api_client.get_dynamic_sidecar_client(app)
        nodes_failed_to_save: list[NodeIDStr] = []
        for node_uuid, node_content in project_at_db.workbench.items():
            # onl dynamic-sidecars are used
            if not await requires_dynamic_sidecar(
                service_key=node_content.key,
                service_version=node_content.version,
                director_v0_client=DirectorV0Client.instance(app),
            ):
                continue

            try:
                await _save_node_state(
                    app,
                    dynamic_sidecar_client,
                    retry_save,
                    node_uuid,
                    node_content.label,
                )
            except Exception:  # pylint: disable=broad-except
                nodes_failed_to_save.append(node_uuid)

    if nodes_failed_to_save:
        typer.echo(
            "The following nodes failed to save:"
            + "\n- "
            + "\n- ".join(nodes_failed_to_save)
            + "\nPlease try to save them individually!"
        )
        sys.exit(1)

    typer.echo(f"Save complete for project {project_id}")


@main.command()
def project_save_state(
    project_id: ProjectID, retry_save: int = DEFAULT_NODE_SAVE_RETRY
):
    """
    Saves the state of all dy-sidecars in a project.
    In case of error while saving the state of an individual node,
    it will retry to save.
    If errors persist it will produce a list of nodes which failed to save.
    """
    asyncio.run(_async_project_save_state(project_id, retry_save))


async def _async_node_save_state(node_id: NodeID, retry_save: int) -> None:
    async with _initialized_app() as app:
        dynamic_sidecar_client = api_client.get_dynamic_sidecar_client(app)
        await _save_node_state(
            app, dynamic_sidecar_client, retry_save, NodeIDStr(f"{node_id}")
        )

    typer.echo(f"Node {node_id} save completed")


@main.command()
def node_save_state(node_id: NodeID, retry_save: int = DEFAULT_NODE_SAVE_RETRY):
    """
    Saves the state of an individual node in the project.
    """
    asyncio.run(_async_node_save_state(node_id, retry_save))
