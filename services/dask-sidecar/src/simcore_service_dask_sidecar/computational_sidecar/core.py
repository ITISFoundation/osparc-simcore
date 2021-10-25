import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pformat
from types import TracebackType
from typing import Any, Awaitable, Dict, List, Optional, Type
from uuid import uuid4

import fsspec
from aiodocker import Docker
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import (
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from distributed import Pub
from models_library.projects_state import RunningState
from packaging import version
from pydantic import ValidationError
from pydantic.networks import AnyUrl
from yarl import URL

from ..boot_mode import BootMode
from ..dask_utils import create_dask_worker_logger, publish_event, publish_task_logs
from ..file_utils import copy_file_to_remote
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
    _state_pub: Pub = field(init=False)
    _progress_pub: Pub = field(init=False)
    _logs_pub: Pub = field(init=False)

    def __post_init__(self) -> None:
        # NOTE: this must be created after the task is started to ensure we do have a dask worker
        self._state_pub = Pub(name=TaskStateEvent.topic_name())
        self._progress_pub = Pub(name=TaskProgressEvent.topic_name())
        self._logs_pub = Pub(name=TaskLogEvent.topic_name())

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
        for input_key, input_params in self.input_data.items():
            if isinstance(input_params, FileUrl):
                destination_path = task_volumes.inputs_folder / (
                    input_params.file_mapping or URL(input_params.url).path.strip("/")
                )
                with fsspec.open(f"{input_params.url}") as src, destination_path.open(
                    "wb"
                ) as dest:
                    dest.write(src.read())

                logger.info("wrote input file %s", destination_path)

            else:
                input_data[input_key] = input_params
        input_data_file.write_text(json.dumps(input_data))

        logger.info(
            "wrote inputs data file in %s, containing %s",
            input_data_file,
            pformat(input_data),
        )

    async def _retrieve_output_data(
        self,
        task_volumes: TaskSharedVolumes,
        integration_version: version.Version,
    ) -> TaskOutputData:
        try:
            logger.debug(
                "following files are located in output folder %s:\n%s",
                task_volumes.outputs_folder,
                pformat(list(task_volumes.outputs_folder.rglob("*"))),
            )
            logger.debug(
                "following outputs will be searched for:\n%s",
                pformat(self.output_data_keys.dict()),
            )
            output_data = TaskOutputData.from_task_output(
                self.output_data_keys,
                task_volumes.outputs_folder,
                "outputs.json"
                if integration_version > LEGACY_INTEGRATION_VERSION
                else "output.json",
            )
            for output_params in output_data.values():
                if isinstance(output_params, FileUrl):
                    src_path = task_volumes.outputs_folder / (
                        output_params.file_mapping
                        or URL(output_params.url).path.strip("/")
                    )
                    await copy_file_to_remote(src_path, output_params.url)

                    logger.info("retrieved output file %s", src_path)
            logger.info("retrieved outputs data:\n%s", pformat(output_data.dict()))
            return output_data

        except ValidationError as exc:
            raise ServiceBadFormattedOutputError(
                self.service_key, self.service_version
            ) from exc

    async def run(self, command: List[str]) -> TaskOutputData:
        publish_event(
            self._state_pub, TaskStateEvent.from_dask_worker(state=RunningState.STARTED)
        )
        publish_event(
            self._logs_pub,
            TaskLogEvent.from_dask_worker(
                log=f"[sidecar] Starting task for {self.service_key}:{self.service_version}..."
            ),
        )

        settings = Settings.create_from_envs()
        run_id = f"{uuid4()}"
        async with Docker() as docker_client, TaskSharedVolumes(
            Path(f"{settings.SIDECAR_COMP_SERVICES_SHARED_FOLDER}/{run_id}")
        ) as task_volumes:
            publish_event(
                self._logs_pub,
                TaskLogEvent.from_dask_worker(
                    log=f"[sidecar] Pulling image for {self.service_key}:{self.service_version}..."
                ),
            )
            await pull_image(
                docker_client, self.docker_auth, self.service_key, self.service_version
            )
            publish_event(
                self._logs_pub,
                TaskLogEvent.from_dask_worker(log="[sidecar] Image pulled."),
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
            logger.debug("Container configuration: \n%s", pformat(config.dict()))

            # set up the inputs
            await self._write_input_data(task_volumes, integration_version)
            publish_event(
                self._logs_pub,
                TaskLogEvent.from_dask_worker(log="[sidecar] Configuration done."),
            )

            # run the image
            async with managed_container(docker_client, config) as container:
                async with managed_monitor_container_log_task(
                    container=container,
                    service_key=self.service_key,
                    service_version=self.service_version,
                    progress_pub=self._progress_pub,
                    logs_pub=self._logs_pub,
                    integration_version=integration_version,
                    task_volumes=task_volumes,
                    log_file_url=self.log_file_url,
                ):
                    publish_event(
                        self._logs_pub,
                        TaskLogEvent.from_dask_worker(
                            log="[sidecar] Starting container..."
                        ),
                    )
                    # run the container
                    await container.start()
                    # get the logs
                    # wait until the container finished, either success or fail or timeout
                    while (container_data := await container.show())["State"][
                        "Running"
                    ]:
                        await asyncio.sleep(CONTAINER_WAIT_TIME_SECS)
                    if container_data["State"]["ExitCode"] > 0:
                        publish_event(
                            self._state_pub,
                            TaskStateEvent.from_dask_worker(
                                state=RunningState.FAILED,
                                msg=f"error while running container {container.id} for {self.service_key}:{self.service_version}",
                            ),
                        )
                        publish_event(
                            self._logs_pub,
                            TaskLogEvent.from_dask_worker(
                                log=f"[sidecar] task failed with exit code{container_data['State']['ExitCode']}"
                            ),
                        )

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
            results = await self._retrieve_output_data(
                task_volumes, integration_version
            )
            publish_event(
                self._logs_pub,
                TaskLogEvent.from_dask_worker(
                    log="[sidecar] task completed successfully"
                ),
            )
            return results

    async def __aenter__(self) -> "ComputationalSidecar":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Awaitable[Optional[bool]]:
        ...
