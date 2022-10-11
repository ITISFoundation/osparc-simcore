import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

import rich
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import AnyHttpUrl, PositiveFloat, parse_obj_as
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    ProgressMessage,
    ProgressPercent,
    TaskId,
    periodic_task_result,
    setup,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from ._client import ThinDV2LocalhostClient

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
    state_save_retry_attempts: int,
    outputs_push_retry_attempts: int,
    update_interval: int,
) -> None:
    async with _minimal_app() as app:
        thin_dv2_localhost_client = ThinDV2LocalhostClient()

        client = Client(
            app=app,
            async_client=thin_dv2_localhost_client.client,
            base_url=parse_obj_as(AnyHttpUrl, thin_dv2_localhost_client.base_address),
        )

        rich.print(f"[red]Cleaning up {node_id}[/red]")
        if not skip_container_removal:
            rich.print("[red][Step][/red] deleting service containers")
            response = await thin_dv2_localhost_client.delete_service_containers(
                f"{node_id}"
            )
            task_id: TaskId = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=5 * _MIN
            )

        if not skip_state_saving:
            rich.print("[red][Step][/red] saving service state")
            async for attempt in AsyncRetrying(
                wait=wait_fixed(1),
                stop=stop_after_attempt(state_save_retry_attempts),
                reraise=True,
            ):
                with attempt:
                    response = await thin_dv2_localhost_client.save_service_state(
                        f"{node_id}"
                    )
                    task_id: TaskId = response.json()
                    await _track_and_display(
                        client, task_id, update_interval, task_timeout=60 * _MIN
                    )

        if not skip_outputs_pushing:
            rich.print("[red][Step][/red] pushing service outputs")
            async for attempt in AsyncRetrying(
                wait=wait_fixed(1),
                stop=stop_after_attempt(outputs_push_retry_attempts),
                reraise=True,
            ):
                with attempt:
                    response = await thin_dv2_localhost_client.push_service_outputs(
                        f"{node_id}"
                    )
                    task_id: TaskId = response.json()
                    await _track_and_display(
                        client, task_id, update_interval, task_timeout=60 * _MIN
                    )

        if not skip_docker_resources_removal:
            rich.print("[red][Step][/red] deleting service docker resources")
            response = await thin_dv2_localhost_client.delete_service_docker_resources(
                f"{node_id}"
            )
            task_id: TaskId = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=5 * _MIN
            )
