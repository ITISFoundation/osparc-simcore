import asyncio
import json
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pformat
from types import TracebackType
from typing import Any, Dict, List, Optional, Type
from uuid import uuid4

from aiodocker import Docker
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import TaskLogEvent, TaskStateEvent
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from models_library.projects_state import RunningState
from packaging import version
from pydantic import ValidationError
from pydantic.networks import AnyUrl
from yarl import URL

from ..boot_mode import BootMode
from ..dask_utils import TaskPublisher, create_dask_worker_logger, publish_event
from ..file_utils import pull_file_from_remote, push_file_to_remote
from ..settings import Settings
from .docker_utils import (
    create_container_config,
    get_computational_shared_data_mount_point,
    get_integration_version,
    managed_container,
    managed_monitor_container_log_task,
    pull_image,
)
from .errors import ServiceBadFormattedOutputError, ServiceRunError
from .models import LEGACY_INTEGRATION_VERSION
from .task_shared_volume import TaskSharedVolumes

logger = create_dask_worker_logger(__name__)
CONTAINER_WAIT_TIME_SECS = 2


@dataclass
class ComputationalSidecar:  # pylint: disable=too-many-instance-attributes
    docker_auth: DockerBasicAuth
    service_key: str
    service_version: str
    input_data: TaskInputData
    output_data_keys: TaskOutputDataSchema
    log_file_url: AnyUrl
    boot_mode: BootMode
    task_max_resources: Dict[str, Any]
    task_publishers: TaskPublisher

    async def _write_input_data(
        self,
        task_volumes: TaskSharedVolumes,
        integration_version: version.Version,
    ) -> None:
        input_data_file = (
            task_volumes.inputs_folder
            / f"{'inputs' if integration_version > LEGACY_INTEGRATION_VERSION else 'input'}.json"
        )
        input_data = {}
        download_tasks = []

        for input_key, input_params in self.input_data.items():
            if isinstance(input_params, FileUrl):
                file_name = (
                    input_params.file_mapping
                    or Path(URL(input_params.url).path.strip("/")).name
                )

                destination_path = task_volumes.inputs_folder / file_name

                if destination_path.parent != task_volumes.inputs_folder:
                    # NOTE: only 'task_volumes.inputs_folder' part of 'destination_path' is guaranteed,
                    # if extra subfolders via file-mapping,
                    # then we make them first
                    destination_path.parent.mkdir(parents=True)

                download_tasks.append(
                    pull_file_from_remote(
                        input_params.url, destination_path, self._publish_sidecar_log
                    )
                )
            else:
                input_data[input_key] = input_params
        await asyncio.gather(*download_tasks)
        input_data_file.write_text(json.dumps(input_data))

        await self._publish_sidecar_log("All the input data were downloaded.")

    async def _retrieve_output_data(
        self,
        task_volumes: TaskSharedVolumes,
        integration_version: version.Version,
    ) -> TaskOutputData:
        try:
            await self._publish_sidecar_log("Retrieving output data...")
            logger.debug(
                "following files are located in output folder %s:\n%s",
                task_volumes.outputs_folder,
                pformat(list(task_volumes.outputs_folder.rglob("*"))),
            )
            logger.debug(
                "following outputs will be searched for:\n%s",
                self.output_data_keys.json(indent=1),
            )

            output_data = TaskOutputData.from_task_output(
                self.output_data_keys,
                task_volumes.outputs_folder,
                "outputs.json"
                if integration_version > LEGACY_INTEGRATION_VERSION
                else "output.json",
            )

            upload_tasks = []
            for output_params in output_data.values():
                if isinstance(output_params, FileUrl):
                    assert (  # nosec
                        output_params.file_mapping
                    ), f"{output_params.json(indent=1)} expected resolved in TaskOutputData.from_task_output"

                    src_path = task_volumes.outputs_folder / output_params.file_mapping
                    upload_tasks.append(
                        push_file_to_remote(
                            src_path, output_params.url, self._publish_sidecar_log
                        )
                    )
            await asyncio.gather(*upload_tasks)

            await self._publish_sidecar_log("All the output data were uploaded.")
            logger.info("retrieved outputs data:\n%s", output_data.json(indent=1))
            return output_data

        except ValidationError as exc:
            raise ServiceBadFormattedOutputError(
                self.service_key, self.service_version
            ) from exc

    async def _publish_sidecar_log(self, log: str) -> None:
        publish_event(
            self.task_publishers.logs,
            TaskLogEvent.from_dask_worker(log=f"[sidecar] {log}"),
        )
        logger.info(log)

    async def _publish_sidecar_state(
        self, state: RunningState, msg: Optional[str] = None
    ) -> None:
        publish_event(
            self.task_publishers.state,
            TaskStateEvent.from_dask_worker(state=state, msg=msg),
        )

    async def run(self, command: List[str]) -> TaskOutputData:
        await self._publish_sidecar_state(RunningState.STARTED)
        await self._publish_sidecar_log(
            f"Starting task for {self.service_key}:{self.service_version} on {socket.gethostname()}..."
        )

        settings = Settings.create_from_envs()
        run_id = f"{uuid4()}"
        async with Docker() as docker_client, TaskSharedVolumes(
            Path(f"{settings.SIDECAR_COMP_SERVICES_SHARED_FOLDER}/{run_id}")
        ) as task_volumes:
            # PRE-PROCESSING
            await pull_image(
                docker_client,
                self.docker_auth,
                self.service_key,
                self.service_version,
                self._publish_sidecar_log,
            )

            integration_version = await get_integration_version(
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
                boot_mode=self.boot_mode,
                task_max_resources=self.task_max_resources,
            )
            await self._write_input_data(task_volumes, integration_version)

            # PROCESSING
            async with managed_container(docker_client, config) as container:
                async with managed_monitor_container_log_task(
                    container=container,
                    service_key=self.service_key,
                    service_version=self.service_version,
                    progress_pub=self.task_publishers.progress,
                    logs_pub=self.task_publishers.logs,
                    integration_version=integration_version,
                    task_volumes=task_volumes,
                    log_file_url=self.log_file_url,
                    log_publishing_cb=self._publish_sidecar_log,
                ):
                    await container.start()
                    await self._publish_sidecar_log(
                        f"Container started as '{container.id}' on {socket.gethostname()}..."
                    )
                    # wait until the container finished, either success or fail or timeout
                    while (container_data := await container.show())["State"][
                        "Running"
                    ]:
                        await asyncio.sleep(CONTAINER_WAIT_TIME_SECS)
                    if container_data["State"]["ExitCode"] > os.EX_OK:
                        await self._publish_sidecar_state(
                            RunningState.FAILED,
                            msg=f"error while running container '{container.id}' for '{self.service_key}:{self.service_version}'",
                        )

                        raise ServiceRunError(
                            self.service_key,
                            self.service_version,
                            container.id,
                            container_data["State"]["ExitCode"],
                            await container.log(stdout=True, stderr=True, tail=20),
                        )
                    await self._publish_sidecar_log("Container ran successfully.")

            # POST-PROCESSING
            results = await self._retrieve_output_data(
                task_volumes, integration_version
            )
            await self._publish_sidecar_log("Task completed successfully.")
            return results

    async def __aenter__(self) -> "ComputationalSidecar":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        if exc:
            await self._publish_sidecar_log(f"Task error:\n{exc}")
            await self._publish_sidecar_log(
                "There might be more information in the service log file"
            )
