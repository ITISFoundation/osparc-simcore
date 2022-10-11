from contextlib import asynccontextmanager

from typing import AsyncIterator
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from pydantic import AnyHttpUrl, PositiveFloat, parse_obj_as
import rich

from ._client import ThinDv2LocalhostClient


from servicelib.fastapi.long_running_tasks.client import (
    Client,
    ProgressMessage,
    ProgressPercent,
    TaskId,
    periodic_task_result,
    setup,
)

from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
import logging


_MIN: Final[PositiveFloat] = 60

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _minimal_app() -> AsyncIterator[FastAPI]:
    app = FastAPI()

    setup(app)

    await app.router.startup()
    yield app
    await app.router.shutdown()


async def _track_and_display(
    client: Client,
    task_id: TaskId,
    update_interval: PositiveFloat,
    task_timeout: PositiveFloat,
):
    with Progress(
        BarColumn(),
        TaskProgressColumn(
            text_format="[progress.percentage]{task.percentage:>3.02f}%"
        ),
        TimeElapsedColumn(),
        TextColumn("[progress.description]{task.description}"),
        refresh_per_second=4,
    ) as progress:
        task = progress.add_task("", total=1.0)

        async def _debug_progress_callback(
            message: ProgressMessage, percent: ProgressPercent, _: TaskId
        ) -> None:
            progress.update(task, completed=percent, description=message)

        async with periodic_task_result(
            client,
            task_id,
            task_timeout=task_timeout,
            progress_callback=_debug_progress_callback,
            status_poll_interval=update_interval,
        ):
            pass


async def async_close_and_save_service(
    node_id: NodeID,
    skip_container_removal: bool,
    skip_state_saving: bool,
    skip_outputs_pushing: bool,
    skip_docker_resources_removal: bool,
    state_retry: int,
    outputs_retry: int,
    update_interval: int,
) -> None:
    async with _minimal_app() as app:
        thin_dv2_localhost_client = ThinDv2LocalhostClient()

        client = Client(
            app=app,
            async_client=thin_dv2_localhost_client.client,
            base_url=parse_obj_as(AnyHttpUrl, thin_dv2_localhost_client.base_address),
        )

        if not skip_container_removal:
            rich.print("deleting service containers")
            response = await thin_dv2_localhost_client.delete_service_containers(
                f"{node_id}"
            )
            task_id: TaskId = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=5 * _MIN
            )

        if not skip_state_saving:
            # TODO add retry here
            rich.print("saving service state")
            response = await thin_dv2_localhost_client.save_service_state(f"{node_id}")
            task_id: TaskId = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=60 * _MIN
            )

        if not skip_outputs_pushing:
            # TODO add retry here
            rich.print("pushing service outputs")
            response = await thin_dv2_localhost_client.push_service_outputs(
                f"{node_id}"
            )
            task_id: TaskId = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=60 * _MIN
            )

        if not skip_docker_resources_removal:
            rich.print("deleting service docker resources")
            response = await thin_dv2_localhost_client.delete_service_docker_resources(
                f"{node_id}"
            )
            task_id: TaskId = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=5 * _MIN
            )
