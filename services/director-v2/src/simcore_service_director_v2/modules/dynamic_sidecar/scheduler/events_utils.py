from collections import deque
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Deque, Optional

from fastapi import FastAPI
from pydantic import AnyHttpUrl

from ....api.dependencies.database import get_base_repository
from ....models.schemas.dynamic_services import DockerContainerInspect
from ....models.schemas.dynamic_services.scheduler import DockerStatus
from ....modules.db.repositories import BaseRepository
from ....modules.director_v0 import DirectorV0Client
from ..api_client import DynamicSidecarClient


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
    app: FastAPI, repo_type: type[BaseRepository]
) -> BaseRepository:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)


def get_director_v0_client(app: FastAPI) -> DirectorV0Client:
    client = DirectorV0Client.instance(app)
    return client


def parse_containers_inspect(
    containers_inspect: Optional[dict[str, Any]]
) -> list[DockerContainerInspect]:
    results: Deque[DockerContainerInspect] = deque()

    if containers_inspect is None:
        return []

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        results.append(DockerContainerInspect.from_container(container_inspect_data))
    return list(results)


def all_containers_running(containers_inspect: list[DockerContainerInspect]) -> bool:
    return len(containers_inspect) > 0 and all(
        x.status == DockerStatus.RUNNING for x in containers_inspect
    )
