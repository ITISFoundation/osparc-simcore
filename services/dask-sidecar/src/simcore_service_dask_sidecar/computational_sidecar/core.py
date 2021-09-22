import asyncio
import json
import shutil
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from types import TracebackType
from typing import AsyncIterator, Awaitable, List, Optional, Type
from uuid import uuid4

import fsspec
from aiodocker import Docker
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from pydantic import ValidationError
from yarl import URL

from ..settings import Settings
from ..utils import create_dask_worker_logger
from .docker_utils import (
    create_container_config,
    get_computational_shared_data_mount_point,
    managed_container,
    managed_monitor_container_log_task,
    pull_image,
)
from .errors import ServiceBadFormattedOutputError, ServiceRunError
from .task_shared_volume import TaskSharedVolumes

logger = create_dask_worker_logger(__name__)
CONTAINER_WAIT_TIME_SECS = 2


@asynccontextmanager
async def managed_task_volumes(base_path: Path) -> AsyncIterator[TaskSharedVolumes]:
    task_shared_volume = None
    try:
        task_shared_volume = TaskSharedVolumes(
            base_path / "inputs", base_path / "outputs", base_path / "logs"
        )
        task_shared_volume.create()
        yield task_shared_volume
    finally:

        def log_error(_, path, excinfo):
            logger.warning(
                "Failed to remove %s [reason: %s]. Should consider pruning files in host later",
                path,
                excinfo,
            )

        shutil.rmtree(base_path, onerror=log_error)


@dataclass
class ComputationalSidecar:
    docker_auth: DockerBasicAuth
    service_key: str
    service_version: str
    input_data: TaskInputData
    output_data_keys: TaskOutputDataSchema

    async def _write_input_data(self, task_volumes: TaskSharedVolumes) -> None:
        input_data_file = task_volumes.input_folder / "inputs.json"
        input_data = {}
        for input_key, input_params in self.input_data.items():
            if isinstance(input_params, FileUrl):
                openfile = fsspec.open(f"{input_params.url}")
                destination_path = task_volumes.input_folder / (
                    input_params.file_mapping or URL(input_params.url).path.strip("/")
                )
                with openfile as src, destination_path.open("wb") as dest:
                    dest.write(src.read())

            else:
                input_data[input_key] = input_params
        input_data_file.write_text(json.dumps(input_data))

    async def _retrieve_output_data(
        self, task_volumes: TaskSharedVolumes
    ) -> TaskOutputData:
        try:
            return TaskOutputData.from_task_output(
                self.output_data_keys, task_volumes.output_folder
            )
        except ValidationError as exc:
            raise ServiceBadFormattedOutputError(
                self.service_key, self.service_version
            ) from exc

    async def run(self, command: List[str]) -> TaskOutputData:
        settings = Settings.create_from_envs()
        run_id = f"{uuid4()}"
        async with Docker() as docker_client, managed_task_volumes(
            Path(f"{settings.SIDECAR_COMP_SERVICES_SHARED_FOLDER}/{run_id}")
        ) as task_volumes:
            await pull_image(
                docker_client, self.docker_auth, self.service_key, self.service_version
            )
            computational_shared_data_mount_point = (
                await get_computational_shared_data_mount_point(docker_client)
            )
            config = await create_container_config(
                docker_registry=self.docker_auth.server_address,
                service_key=self.service_key,
                service_version=self.service_version,
                command=command,
                comp_volume_mount_point=f"{computational_shared_data_mount_point}/{run_id}",
            )
            logger.debug("Container configuration: \n%s", pformat(config.dict()))

            # set up the inputs
            await self._write_input_data(task_volumes)

            # run the image
            async with managed_container(docker_client, config) as container:
                async with managed_monitor_container_log_task(
                    container, self.service_key, self.service_version
                ):
                    # run the container
                    await container.start()
                    # get the logs

                    # wait until the container finished, either success or fail or timeout
                    while (container_data := await container.show())["State"][
                        "Running"
                    ]:
                        await asyncio.sleep(CONTAINER_WAIT_TIME_SECS)
                    if container_data["State"]["ExitCode"] > 0:
                        # the container had an error
                        raise ServiceRunError(
                            self.service_key,
                            self.service_version,
                            container.id,
                            container_data["State"]["ExitCode"],
                            await container.log(stdout=True, stderr=True, tail=20),
                        )
                    logger.info(
                        "%s:%s - %s completed successfully",
                        self.service_key,
                        self.service_version,
                        container.id,
                    )
            # get the outputs
            return await self._retrieve_output_data(task_volumes)

    async def __aenter__(self) -> "ComputationalSidecar":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Awaitable[Optional[bool]]:
        ...
