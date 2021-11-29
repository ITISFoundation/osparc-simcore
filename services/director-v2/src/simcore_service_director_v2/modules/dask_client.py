import asyncio
import functools
import json
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Tuple

import dask.distributed
import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import (
    TaskCancelEvent,
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic.networks import AnyUrl
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.wait import wait_fixed

from ..core.errors import ConfigurationError
from ..core.settings import DaskSchedulerSettings
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import ClusterID, UserID
from ..utils.dask import (
    UserCompleteCB,
    check_client_can_connect_to_scheduler,
    check_if_cluster_is_able_to_run_pipeline,
    compute_input_data,
    compute_output_data_schema,
    compute_service_log_file_upload_link,
    dask_sub_consumer_task,
    done_dask_callback,
    from_node_reqs_to_dask_resources,
    generate_dask_job_id,
)

logger = logging.getLogger(__name__)
CLUSTER_RESOURCE_MOCK_USAGE: float = 1e-9


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    async def on_startup() -> None:
        await DaskClient.create(
            app,
            settings=settings,
        )

    async def on_shutdown() -> None:
        if app.state.dask_client:
            await app.state.dask_client.delete()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class DaskClient:
    app: FastAPI
    client: distributed.Client
    settings: DaskSchedulerSettings
    cancellation_dask_pub: distributed.Pub

    _taskid_to_future_map: Dict[str, distributed.Future] = field(default_factory=dict)
    _subscribed_tasks: List[asyncio.Task] = field(default_factory=list)

    @classmethod
    async def create(
        cls, app: FastAPI, settings: DaskSchedulerSettings
    ) -> "DaskClient":
        logger.info(
            "Initiating connection to %s",
            f"dask-scheduler at {settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
        )
        async for attempt in AsyncRetrying(
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.WARNING),
            wait=wait_fixed(2),
            retry=retry_if_exception_type(),
        ):
            with attempt:
                dask_client = await distributed.Client(
                    f"tcp://{settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
                    asynchronous=True,
                    name=f"director-v2_{socket.gethostname()}_{os.getpid()}",
                )
                check_client_can_connect_to_scheduler(dask_client)
                app.state.dask_client = cls(
                    app=app,
                    client=dask_client,
                    settings=settings,
                    cancellation_dask_pub=distributed.Pub(TaskCancelEvent.topic_name()),
                )
                logger.info(
                    "Connection to %s succeeded [%s]",
                    f"dask-scheduler at {settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
                )
                logger.info(
                    "Client is connected to scheduler: %s",
                    json.dumps(dask_client.scheduler_info(), indent=2),
                )
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "DaskClient":
        if not hasattr(app.state, "dask_client"):
            raise ConfigurationError(
                "Dask client is not available. Please check the configuration."
            )
        return app.state.dask_client

    async def delete(self) -> None:
        logger.debug("closing dask client...")
        for task in self._subscribed_tasks:
            task.cancel()
        await asyncio.gather(*self._subscribed_tasks, return_exceptions=True)
        await self.client.close()  # type: ignore
        logger.info("dask client properly closed")

    def register_handlers(
        self,
        task_change_handler: Callable[[str], Awaitable[None]],
        task_progress_handler: Callable[[str], Awaitable[None]],
        task_log_handler: Callable[[str], Awaitable[None]],
    ) -> None:
        _EVENT_CONSUMER_MAP = [
            (TaskStateEvent, task_change_handler),
            (TaskProgressEvent, task_progress_handler),
            (TaskLogEvent, task_log_handler),
        ]
        self._subscribed_tasks = [
            asyncio.create_task(
                dask_sub_consumer_task(event, handler),
                name=f"{event.topic_name()}_dask_sub_consumer_task",
            )
            for event, handler in _EVENT_CONSUMER_MAP
        ]

    async def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks: Dict[NodeID, Image],
        callback: UserCompleteCB,
        remote_fct: Callable = None,
    ) -> List[Tuple[NodeID, str]]:
        """actually sends the function remote_fct to be remotely executed. if None is kept then the default
        function that runs container will be started."""

        def _comp_sidecar_fct(
            docker_auth: DockerBasicAuth,
            service_key: str,
            service_version: str,
            input_data: TaskInputData,
            output_data_keys: TaskOutputDataSchema,
            log_file_url: AnyUrl,
            command: List[str],
        ) -> TaskOutputData:
            """This function is serialized by the Dask client and sent over to the Dask sidecar(s)
            Therefore, (screaming here) DO NOT MOVE THAT IMPORT ANYWHERE ELSE EVER!!"""
            from simcore_service_dask_sidecar.tasks import (  # type: ignore
                run_computational_sidecar,
            )

            return run_computational_sidecar(
                docker_auth,
                service_key,
                service_version,
                input_data,
                output_data_keys,
                log_file_url,
                command,
            )

        if remote_fct is None:
            remote_fct = _comp_sidecar_fct
        list_of_node_id_to_job_id: List[Tuple[NodeID, str]] = []
        for node_id, node_image in tasks.items():
            job_id = generate_dask_job_id(
                service_key=node_image.name,
                service_version=node_image.tag,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
            )
            dask_resources = from_node_reqs_to_dask_resources(
                node_image.node_requirements
            )
            # add the cluster ID here
            dask_resources.update(
                {
                    f"{self.settings.DASK_CLUSTER_ID_PREFIX}{cluster_id}": CLUSTER_RESOURCE_MOCK_USAGE
                }
            )

            check_client_can_connect_to_scheduler(self.client)
            check_if_cluster_is_able_to_run_pipeline(
                node_id=node_id,
                scheduler_info=self.client.scheduler_info(),
                task_resources=dask_resources,
                node_image=node_image,
                cluster_id_prefix=self.settings.DASK_CLUSTER_ID_PREFIX,  # type: ignore
                cluster_id=cluster_id,
            )

            input_data = await compute_input_data(
                self.app, user_id, project_id, node_id
            )
            output_data_keys = await compute_output_data_schema(
                self.app, user_id, project_id, node_id
            )
            log_file_url = await compute_service_log_file_upload_link(
                user_id, project_id, node_id
            )
            try:
                task_future = self.client.submit(
                    remote_fct,
                    docker_auth=DockerBasicAuth(
                        server_address=self.app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY.resolved_registry_url,
                        username=self.app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_USER,
                        password=self.app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_PW,
                    ),
                    service_key=node_image.name,
                    service_version=node_image.tag,
                    input_data=input_data,
                    output_data_keys=output_data_keys,
                    log_file_url=log_file_url,
                    command=["run"],
                    key=job_id,
                    resources=dask_resources,
                    retries=0,
                )
                task_future.add_done_callback(
                    functools.partial(
                        done_dask_callback,
                        task_to_future_map=self._taskid_to_future_map,
                        user_callback=callback,
                        main_loop=asyncio.get_event_loop(),
                    )
                )

                self._taskid_to_future_map[job_id] = task_future
                list_of_node_id_to_job_id.append((node_id, job_id))
                dask.distributed.fire_and_forget(
                    task_future
                )  # this should ensure the task will run even if the future goes out of scope
                logger.debug("Dask task %s started", task_future.key)
            except Exception:
                # Dask raises a base Exception here in case of connection error, this will raise a more precise one
                check_client_can_connect_to_scheduler(self.client)
                # if the connection is good, then the problem is different, so we re-raise
                raise
        return list_of_node_id_to_job_id

    async def abort_computation_tasks(self, job_ids: List[str]) -> None:
        logger.debug("cancelling tasks with job_ids: [%s]", job_ids)
        for job_id in job_ids:
            task_future = self._taskid_to_future_map.get(job_id)
            if task_future:
                self.cancellation_dask_pub.put(  # type: ignore
                    TaskCancelEvent(job_id=job_id).json()
                )
                await task_future.cancel()
                logger.debug("Dask task %s cancelled", task_future.key)
