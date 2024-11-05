from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

import rich
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import AnyHttpUrl, PositiveFloat, TypeAdapter
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from servicelib.fastapi.http_client_thin import UnexpectedStatusError
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    ProgressMessage,
    ProgressPercent,
    TaskId,
    periodic_task_result,
    setup,
)
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from ._client import ThinDV2LocalhostClient

_MIN: Final[PositiveFloat] = 60
HEADING: Final[str] = "[green]*[/green]"


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
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("[progress.description]{task.description}"),
        refresh_per_second=4,
    ) as progress:
        task = progress.add_task("...", total=1.0, visible=True)

        async def _debug_progress_callback(
            message: ProgressMessage, percent: ProgressPercent | None, _: TaskId
        ) -> None:
            progress.update(task, completed=percent, description=message, visible=True)

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
    disable_observation_attempts: int,
    state_save_retry_attempts: int,
    outputs_push_retry_attempts: int,
    update_interval: int,
) -> None:
    task_id: TaskId
    async with _minimal_app() as app, ThinDV2LocalhostClient() as thin_dv2_localhost_client:
        rich.print(
            f"[yellow]Starting[/yellow] cleanup for service [green]{node_id}[/green]"
        )

        rich.print(f"{HEADING} disabling service observation")
        async for attempt in AsyncRetrying(
            wait=wait_fixed(1),
            stop=stop_after_attempt(disable_observation_attempts),
            retry=retry_if_exception_type(UnexpectedStatusError),
            reraise=True,
        ):
            with attempt:
                await thin_dv2_localhost_client.toggle_service_observation(
                    f"{node_id}", is_disabled=True
                )

        client = Client(
            app=app,
            async_client=thin_dv2_localhost_client.client,
            base_url=f"{TypeAdapter(AnyHttpUrl).validate_python(thin_dv2_localhost_client.BASE_ADDRESS)}",
        )

        if not skip_container_removal:
            rich.print(f"{HEADING} deleting service containers")
            response = await thin_dv2_localhost_client.delete_service_containers(
                f"{node_id}"
            )
            task_id = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=5 * _MIN
            )

        if not skip_state_saving:
            rich.print(f"{HEADING} saving service state")
            async for attempt in AsyncRetrying(
                wait=wait_fixed(1),
                stop=stop_after_attempt(state_save_retry_attempts),
                reraise=True,
            ):
                with attempt:
                    response = await thin_dv2_localhost_client.save_service_state(
                        f"{node_id}"
                    )
                    task_id = response.json()
                    await _track_and_display(
                        client, task_id, update_interval, task_timeout=60 * _MIN
                    )

        if not skip_outputs_pushing:
            rich.print(f"{HEADING} pushing service outputs")
            async for attempt in AsyncRetrying(
                wait=wait_fixed(1),
                stop=stop_after_attempt(outputs_push_retry_attempts),
                reraise=True,
            ):
                with attempt:
                    response = await thin_dv2_localhost_client.push_service_outputs(
                        f"{node_id}"
                    )
                    task_id = response.json()
                    await _track_and_display(
                        client, task_id, update_interval, task_timeout=60 * _MIN
                    )

        if not skip_docker_resources_removal:
            rich.print(
                f"{HEADING} deleting service docker resources and removing service"
            )
            response = await thin_dv2_localhost_client.delete_service_docker_resources(
                f"{node_id}"
            )
            task_id = response.json()
            await _track_and_display(
                client, task_id, update_interval, task_timeout=5 * _MIN
            )
        rich.print(
            f"[green]Finished[/green] cleanup for service [green]{node_id}[/green]"
        )
