import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from json.decoder import JSONDecodeError
from pathlib import Path
from types import TracebackType
from typing import Any, AsyncIterator, Awaitable, Dict, List, Optional, Type
from uuid import uuid4

from aiodocker import Docker
from simcore_service_sidecar.task_shared_volume import TaskSharedVolumes

from ..utils import create_dask_worker_logger
from .docker_utils import (
    create_container_config,
    managed_container,
    managed_monitor_container_log_task,
    pull_image,
)
from .errors import (
    ServiceBadFormattedOutputError,
    ServiceMissingOutputError,
    ServiceRunError,
)

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
        if task_shared_volume:
            task_shared_volume.delete()


@dataclass
class ComputationalSidecar:
    service_key: str
    service_version: str
    input_data: Dict[str, Any]
    output_data_keys: Dict[str, Any]

    async def _write_input_data(self, task_volumes: TaskSharedVolumes) -> None:
        input_data_file = task_volumes.input_folder / "inputs.json"
        input_data_file.write_text(json.dumps(self.input_data))

    async def _retrieve_output_data(
        self, task_volumes: TaskSharedVolumes
    ) -> Dict[str, Any]:
        output_data = {}
        for output_key, output_params in self.output_data_keys.items():
            # path outputs are located in the outputs folder
            if output_params["type"] in [Path, Optional[Path]]:
                # their file names might be the key or the alternative name if it exists
                file_path = task_volumes.output_folder / output_params.get(
                    "name", output_key
                )
                if not file_path.exists():
                    if output_params["type"] == Path:
                        raise ServiceMissingOutputError(
                            self.service_key, self.service_version, output_key
                        )
                    # optional output
                    continue
                output_data[output_key] = file_path
            else:
                # all other outputs should be located in a JSON file
                output_data_file = task_volumes.output_folder / "outputs.json"
                if not output_data_file.exists():
                    if output_params["type"] != Optional[Any]:
                        raise ServiceMissingOutputError(
                            self.service_key, self.service_version, output_key
                        )
                    continue
                try:
                    service_output = json.loads(output_data_file.read_text())
                    if output_key not in service_output:
                        if output_params["type"] != Optional[Any]:
                            raise ServiceMissingOutputError(
                                self.service_key, self.service_version, output_key
                            )
                        continue
                    output_data[output_key] = service_output[output_key]
                except JSONDecodeError as exc:
                    raise ServiceBadFormattedOutputError(
                        self.service_key, self.service_version, output_key
                    ) from exc
        return output_data

    async def run(self, command: List[str]) -> Dict[str, Any]:
        async with Docker() as docker_client, managed_task_volumes(
            Path(f"/tmp/{uuid4()}")
        ) as task_volumes:
            await pull_image(docker_client, self.service_key, self.service_version)

            config = await create_container_config(
                service_key=self.service_key,
                service_version=self.service_version,
                command=command,
                volumes=task_volumes,
            )

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
