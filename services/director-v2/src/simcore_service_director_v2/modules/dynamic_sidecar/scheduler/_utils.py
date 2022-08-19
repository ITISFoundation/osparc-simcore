from collections import deque
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Deque, Dict, List, Optional, Type

from fastapi import FastAPI
from pydantic import AnyHttpUrl

from ....api.dependencies.database import get_base_repository
from ....core.settings import DynamicSidecarSettings
from ....models.schemas.dynamic_services import DockerContainerInspect
from ....models.schemas.dynamic_services.scheduler import DockerStatus, SchedulerData
from ...db.repositories import BaseRepository
from ...director_v0 import DirectorV0Client
from ..api_client import DynamicSidecarClient
from ..docker_api import (
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
    remove_volumes_from_node,
)
from ..volumes import DY_SIDECAR_SHARED_STORE_PATH, DynamicSidecarVolumesPathsResolver


@asynccontextmanager
async def disabled_directory_watcher(
    dynamic_sidecar_client: DynamicSidecarClient, dynamic_sidecar_endpoint: AnyHttpUrl
) -> AsyncIterator[None]:
    try:
        # disable file system event watcher while writing
        # to the outputs directory to avoid data being pushed
        # via nodeports upon change
        await dynamic_sidecar_client.service_disable_dir_watcher(
            dynamic_sidecar_endpoint
        )
        yield
    finally:
        # enable file system event watcher so data from outputs
        # can be again synced via nodeports upon change
        await dynamic_sidecar_client.service_enable_dir_watcher(
            dynamic_sidecar_endpoint
        )


def fetch_repo_outside_of_request(
    app: FastAPI, repo_type: Type[BaseRepository]
) -> BaseRepository:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)


def get_director_v0_client(app: FastAPI) -> DirectorV0Client:
    client = DirectorV0Client.instance(app)
    return client


def parse_containers_inspect(
    containers_inspect: Optional[Dict[str, Any]]
) -> List[DockerContainerInspect]:
    results: Deque[DockerContainerInspect] = deque()

    if containers_inspect is None:
        return []

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        results.append(DockerContainerInspect.from_container(container_inspect_data))
    return list(results)


def all_containers_running(containers_inspect: List[DockerContainerInspect]) -> bool:
    return len(containers_inspect) > 0 and all(
        (x.status == DockerStatus.RUNNING for x in containers_inspect)
    )


async def cleanup_sidecar_stack_and_resources(
    dynamic_sidecar_settings: DynamicSidecarSettings, scheduler_data: SchedulerData
) -> None:
    # remove the 2 services
    await remove_dynamic_sidecar_stack(
        node_uuid=scheduler_data.node_uuid,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
    )
    # remove network
    await remove_dynamic_sidecar_network(scheduler_data.dynamic_sidecar_network_name)

    # Remove all dy-sidecar associated volumes from node
    unique_volume_names = [
        DynamicSidecarVolumesPathsResolver.source(
            path=volume_path,
            node_uuid=scheduler_data.node_uuid,
            run_id=scheduler_data.dynamic_sidecar.run_id,
        )
        for volume_path in [
            DY_SIDECAR_SHARED_STORE_PATH,
            scheduler_data.paths_mapping.inputs_path,
            scheduler_data.paths_mapping.outputs_path,
        ]
        + scheduler_data.paths_mapping.state_paths
    ]
    assert scheduler_data.docker_node_id  # nosec
    # TODO: CHECK THAT manually removing the dy-sidecar, when it is running,
    # it does not remove the volumes. Is this something we want?
    # put a state that keeps track of when data was saved and if that is True, volumes can be removed,
    # otherwise keep them in place!!!!!
    # fix when merging this to https://github.com/ITISFoundation/osparc-simcore/pull/3272
    await remove_volumes_from_node(
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        volume_names=unique_volume_names,
        docker_node_id=scheduler_data.docker_node_id,
        user_id=scheduler_data.user_id,
        project_id=scheduler_data.project_id,
        node_uuid=scheduler_data.node_uuid,
    )
