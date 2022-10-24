import asyncio
import sys
from contextlib import asynccontextmanager
from enum import Enum
from typing import AsyncIterator, Optional

import typer
from fastapi import FastAPI, status
from httpx import AsyncClient, HTTPError
from models_library.projects import NodeIDStr, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceType
from pydantic import AnyHttpUrl, BaseModel, PositiveInt, parse_obj_as
from rich.live import Live
from rich.table import Table
from servicelib.services_utils import get_service_from_key
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random_exponential

from ..core.application import create_base_app
from ..core.settings import AppSettings
from ..models.domains.dynamic_services import DynamicServiceOut
from ..models.schemas.dynamic_services import (
    DynamicSidecarNamesHelper,
    ServiceBootType,
    ServiceState,
)
from ..modules import db, director_v0, dynamic_sidecar
from ..modules.db.repositories.projects import ProjectsRepository
from ..modules.director_v0 import DirectorV0Client
from ..modules.dynamic_sidecar import api_client
from ..modules.dynamic_sidecar.scheduler._utils import get_repository
from ..modules.projects_networks import requires_dynamic_sidecar


@asynccontextmanager
async def _initialized_app(only_db: bool = False) -> AsyncIterator[FastAPI]:
    app = create_base_app()
    settings: AppSettings = app.state.settings

    # Initialize minimal required components for the application
    db.setup(app, settings.POSTGRES)

    if not only_db:
        dynamic_sidecar.setup(app)
        director_v0.setup(app, settings.DIRECTOR_V0)

    await app.router.startup()
    yield app
    await app.router.shutdown()


### PROJECT SAVE STATE


def _get_dynamic_sidecar_endpoint(
    settings: AppSettings, node_id: NodeIDStr
) -> AnyHttpUrl:
    dynamic_sidecar_names = DynamicSidecarNamesHelper.make(NodeID(node_id))
    hostname = dynamic_sidecar_names.service_name_dynamic_sidecar
    port = settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_PORT
    return parse_obj_as(AnyHttpUrl, f"http://{hostname}:{port}")  # NOSONAR


async def _save_node_state(
    app,
    dynamic_sidecar_client: api_client.DynamicSidecarClient,
    save_attempts: int,
    node_uuid: NodeIDStr,
    label: str,
) -> None:
    typer.echo(f"Saving state for {node_uuid} {label}")
    async for attempt in AsyncRetrying(
        wait=wait_random_exponential(),
        stop=stop_after_attempt(save_attempts),
        reraise=True,
    ):
        with attempt:
            typer.echo(f"Attempting to save {node_uuid} {label}")
            await dynamic_sidecar_client.save_service_state(
                _get_dynamic_sidecar_endpoint(app.state.settings, node_uuid)
            )


async def async_project_save_state(project_id: ProjectID, save_attempts: int) -> None:
    async with _initialized_app() as app:
        projects_repository: ProjectsRepository = get_repository(
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
                    save_attempts,
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


### PROJECT STATE


class StatusIcon(str, Enum):
    OK = ":green_heart:"
    ONGOING = ":yellow_heart:"
    FAILED = ":broken_heart:"
    UNKNOWN = ":grey_question:"
    HTTP_ERROR = ":exclamation:"


class RenderData(BaseModel):
    node_uuid: NodeIDStr
    label: str
    status_icon: StatusIcon
    state: str


async def _get_dy_service_state(
    client: AsyncClient, node_uuid: NodeIDStr
) -> Optional[DynamicServiceOut]:
    try:
        result = await client.get(
            f"http://localhost:8000/v2/dynamic_services/{node_uuid}",  # NOSONAR
            timeout=5,
            follow_redirects=True,
        )
    except HTTPError:
        return None

    if result.status_code != status.HTTP_200_OK:
        return None

    result_dict = result.json()
    return DynamicServiceOut(
        **(result_dict["data"] if "data" in result_dict else result_dict)
    )


async def _to_render_data(
    client: AsyncClient, node_uuid: NodeIDStr, label: str, service_type: ServiceType
) -> RenderData:
    if service_type == ServiceType.FRONTEND:
        return RenderData(
            node_uuid=node_uuid,
            label=label,
            status_icon=StatusIcon.OK,
            state="",
        )

    if service_type == ServiceType.COMPUTATIONAL:
        return RenderData(
            node_uuid=node_uuid,
            label=label,
            status_icon=StatusIcon.UNKNOWN,
            state="unknown",
        )

    node_state = await _get_dy_service_state(client, node_uuid)
    if node_state is None:
        return RenderData(
            node_uuid=node_uuid,
            label="",
            status_icon=StatusIcon.HTTP_ERROR,
            state="[red]Not found[/red]",
        )

    state_icon = StatusIcon.ONGOING
    text_color = "yellow"
    if node_state.state == ServiceState.RUNNING:
        state_icon = StatusIcon.OK
        text_color = "green"
    elif node_state.state == ServiceState.FAILED:
        state_icon = StatusIcon.FAILED
        text_color = "red"

    service_type_icon = ""
    if node_state.boot_type == ServiceBootType.V0:
        service_type_icon = ":fax:"
    elif node_state.boot_type == ServiceBootType.V2:
        service_type_icon = ":sparkles:"

    return RenderData(
        node_uuid=node_uuid,
        label=f"{service_type_icon} {label}",
        status_icon=state_icon,
        state=f"[{text_color}]{node_state.state.value}[/{text_color}]",
    )


async def _get_nodes_render_data(
    app: FastAPI,
    project_id: ProjectID,
) -> list[RenderData]:
    projects_repository: ProjectsRepository = get_repository(app, ProjectsRepository)
    project_at_db = await projects_repository.get_project(project_id)

    render_data = []
    async with AsyncClient() as client:
        for node_uuid, node_content in project_at_db.workbench.items():
            service_type = get_service_from_key(service_key=node_content.key)
            render_data.append(
                await _to_render_data(
                    client, node_uuid, node_content.label, service_type
                )
            )
    return sorted(render_data, key=lambda x: x.node_uuid)


async def _display(
    app: FastAPI,
    project_id: ProjectID,
    *,
    update_interval: PositiveInt,
    blocking: bool,
) -> None:
    def generate_table(render_data: list[RenderData]) -> Table:
        table = Table()
        table.add_column("Icon")
        table.add_column("NodeID")
        table.add_column("Label")
        table.add_column("State")

        for entry in render_data:
            table.add_row(
                entry.status_icon,
                entry.node_uuid,
                entry.label,
                entry.state,
            )
        return table

    with Live(generate_table(await _get_nodes_render_data(app, project_id))) as live:
        while blocking:
            await asyncio.sleep(update_interval)
            live.update(generate_table(await _get_nodes_render_data(app, project_id)))


async def async_project_state(
    project_id: ProjectID, blocking: bool, update_interval: PositiveInt
) -> None:
    async with _initialized_app(only_db=True) as app:
        await _display(
            app, project_id, update_interval=update_interval, blocking=blocking
        )
