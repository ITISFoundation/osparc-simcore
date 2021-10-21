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
from yarl import URL

from ..boot_mode import BootMode
from ..dask_utils import create_dask_worker_logger, publish_event
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
from .models import IntegrationVersion
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
        integration_version: IntegrationVersion,
    ) -> None:
        input_data_file = (
            task_volumes.inputs_folder
            / f"{'input' if integration_version == version.parse('0.0.0') else 'inputs'}.json"
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
        integration_version: IntegrationVersion,
    ) -> TaskOutputData:
        try:
            logger.debug(
                "following files are located in output folder %s:\n%s",
                task_volumes.outputs_folder,
                pformat(list(task_volumes.outputs_folder.rglob("*"))),
            )
            logger.debug(
                "following outputs will be searched for: %s",
                pformat(self.output_data_keys),
            )
            output_data = TaskOutputData.from_task_output(
                self.output_data_keys,
                task_volumes.outputs_folder,
                "output.json"
                if integration_version == version.parse("0.0.0")
                else "outputs.json",
            )
            for output_params in output_data.values():
                if isinstance(output_params, FileUrl):
                    src_path = task_volumes.outputs_folder / (
                        output_params.file_mapping
                        or URL(output_params.url).path.strip("/")
                    )
                    if output_params.url.scheme == "http":
                        # NOTE: special case for http scheme when uploading. this is typically a S3 put presigned link.
                        # Therefore, we need to use the http filesystem directly in order to call the put_file function.
                        # writing on httpfilesystem is disabled by default.
                        fs = fsspec.filesystem(
                            "http",
                            headers={
                                "Content-Length": f"{src_path.stat().st_size}",
                            },
                        )
                        fs.put_file(src_path, f"{output_params.url}", method="PUT")
                    else:
                        with src_path.open("rb") as src, fsspec.open(
                            f"{output_params.url}", "wb"
                        ) as dst:
                            dst.write(src.read())

                    logger.info("retrieved output file %s", src_path)
            logger.info("retrieved outputs data %s", pformat(output_data))
            return output_data

        except ValidationError as exc:
            raise ServiceBadFormattedOutputError(
                self.service_key, self.service_version
            ) from exc

    async def run(self, command: List[str]) -> TaskOutputData:
        publish_event(
            self._state_pub, TaskStateEvent.from_dask_worker(state=RunningState.STARTED)
        )

        settings = Settings.create_from_envs()
        run_id = f"{uuid4()}"
        async with Docker() as docker_client, TaskSharedVolumes(
            Path(f"{settings.SIDECAR_COMP_SERVICES_SHARED_FOLDER}/{run_id}")
        ) as task_volumes:
            await pull_image(
                docker_client, self.docker_auth, self.service_key, self.service_version
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
                        publish_event(
                            self._state_pub,
                            TaskStateEvent.from_dask_worker(
                                state=RunningState.FAILED,
                                msg=f"error while running container {container.id} for {self.service_key}:{self.service_version}",
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
            return await self._retrieve_output_data(task_volumes, integration_version)

    async def __aenter__(self) -> "ComputationalSidecar":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Awaitable[Optional[bool]]:
        ...
