import logging
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import parse_obj_as
from servicelib.docker_utils import to_datetime
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ....core.settings import DynamicSidecarSettings
from ....models.schemas.constants import DYNAMIC_VOLUME_REMOVER_PREFIX
from ..docker_service_specs.volume_remover import (
    DockerVersion,
    spec_volume_removal_service,
)
from ._utils import docker_client

log = logging.getLogger(__name__)

# FROM https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
SERVICE_FINISHED_STATES: set[str] = {
    "complete",
    "failed",
    "shutdown",
    "rejected",
    "orphaned",
    "remove",
}


async def remove_volumes_from_node(
    dynamic_sidecar_settings: DynamicSidecarSettings,
    volume_names: list[str],
    docker_node_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    *,
    volume_removal_attempts: int = 15,
    sleep_between_attempts_s: int = 2,
) -> bool:
    """
    Starts a service at target docker node which will remove
    all entries in the `volumes_names` list.
    """

    async with docker_client() as client:
        # When running docker-dind makes sure to use the same image as the
        # underlying docker-engine.
        # Will start a container with the same version across the entire cluster.
        # It is safe to assume the local docker engine version will be
        # the same as the one on the targeted node.
        version_request = await client._query_json(  # pylint: disable=protected-access
            "version", versioned_api=False
        )
        docker_version: DockerVersion = parse_obj_as(
            DockerVersion, version_request["Version"]
        )

        # Timeout for the runtime of the service is calculated based on the amount
        # of attempts required to remove each individual volume,
        # in the worst case scenario when all volumes are do not exit.
        volume_removal_timeout_s = volume_removal_attempts * sleep_between_attempts_s
        service_timeout_s = volume_removal_timeout_s * len(volume_names)

        service_spec = spec_volume_removal_service(
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            docker_node_id=docker_node_id,
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            volume_names=volume_names,
            docker_version=docker_version,
            volume_removal_attempts=volume_removal_attempts,
            sleep_between_attempts_s=sleep_between_attempts_s,
            service_timeout_s=service_timeout_s,
        )

        volume_removal_service = await client.services.create(
            **jsonable_encoder(service_spec, by_alias=True, exclude_unset=True)
        )

        service_id = volume_removal_service["ID"]
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_delay(service_timeout_s),
                wait=wait_fixed(0.5),
                retry=retry_if_exception_type(TryAgain),
                reraise=True,
            ):
                with attempt:
                    tasks = await client.tasks.list(filters={"service": service_id})
                    # NOTE: the service will have at most 1 task, since there is no restart
                    # policy present
                    if len(tasks) != 1:
                        # Docker swarm needs a bit of time to startup the tasks
                        raise TryAgain(
                            f"Expected 1 task for service {service_id}, found {tasks=}"
                        )

                    task = tasks[0]
                    task_status = task["Status"]
                    log.debug("Service %s, %s", service_id, f"{task_status=}")
                    task_state = task_status["State"]
                    if task_state not in SERVICE_FINISHED_STATES:
                        raise TryAgain(f"Waiting for task to finish: {task_status=}")

                    if not (
                        task_state == "complete"
                        and task_status["ContainerStatus"]["ExitCode"] == 0
                    ):
                        log.error(
                            "Service %s status: %s", service_id, f"{task_status=}"
                        )
                        # NOTE: above implies the volumes will remain in the system and
                        # have to be manually removed.
                        return False
        finally:
            # NOTE: services created in swarm need to be removed, there is no way
            # to instruct swarm to remove a service after it's created
            # container/task finished
            await client.services.delete(service_id)

        return True


async def remove_pending_volume_removal_services(
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> None:
    """
    Removes all pending volume removal services. Such a service
    will be considered pending if it is running for longer than its
    intended duration (defined in the `service_timeout_s` label).
    """
    service_filters = {
        "label": [
            f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
        ],
        "name": [f"{DYNAMIC_VOLUME_REMOVER_PREFIX}"],
    }
    async with docker_client() as client:
        volume_removal_services = await client.services.list(filters=service_filters)

        for volume_removal_service in volume_removal_services:
            service_timeout_s = int(
                volume_removal_service["Spec"]["Labels"]["service_timeout_s"]
            )
            created_at = to_datetime(volume_removal_services[0]["CreatedAt"])
            time_diff = datetime.now(timezone.utc) - created_at
            service_timed_out = time_diff.seconds > (service_timeout_s * 10)
            if service_timed_out:
                service_id = volume_removal_service["ID"]
                service_name = volume_removal_service["Spec"]["Name"]
                log.debug("Removing pending volume removal service %s", service_name)
                await client.services.delete(service_id)
