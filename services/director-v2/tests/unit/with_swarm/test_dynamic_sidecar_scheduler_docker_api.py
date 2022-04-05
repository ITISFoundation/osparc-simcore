# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from typing import AsyncIterable

import aiodocker
import pytest
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL,
)
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    DockerContainerInspect,
    SchedulerData,
    SimcoreServiceLabels,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api import (
    update_scheduler_data_label,
)


@pytest.fixture
def service_name() -> str:
    return "mock-service-name"


@pytest.fixture(
    params=[
        SimcoreServiceLabels.parse_obj(example)
        for example in SimcoreServiceLabels.Config.schema_extra["examples"]
    ],
)
def labels_example(request) -> SimcoreServiceLabels:
    return request.param


@pytest.fixture
def mock_scheduler_data(
    labels_example: SimcoreServiceLabels,
    scheduler_data: SchedulerData,
    service_name: str,
) -> SchedulerData:
    # test all possible cases
    if labels_example.paths_mapping is not None:
        scheduler_data.paths_mapping = labels_example.paths_mapping
    scheduler_data.compose_spec = labels_example.compose_spec
    scheduler_data.container_http_entry = labels_example.container_http_entry
    scheduler_data.restart_policy = labels_example.restart_policy

    scheduler_data.dynamic_sidecar.containers_inspect = [
        DockerContainerInspect.from_container(
            {"State": {"Status": "dead"}, "Name": "mock_name", "Id": "mock_id"}
        )
    ]
    scheduler_data.service_name = service_name
    return scheduler_data


@pytest.fixture
async def docker() -> AsyncIterable[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
async def mock_service(
    docker: aiodocker.Docker, service_name: str
) -> AsyncIterable[str]:
    service_data = await docker.services.create(
        {"ContainerSpec": {"Image": "joseluisq/static-web-server:1.16.0-alpine"}},
        name=service_name,
    )

    yield service_name

    await docker.services.delete(service_data["ID"])


async def test_update_scheduler_data_label(
    docker: aiodocker.Docker,
    mock_service: str,
    mock_scheduler_data: SchedulerData,
    docker_swarm: None,
) -> None:
    await update_scheduler_data_label(mock_scheduler_data)

    # fetch stored data in labels
    service_inspect = await docker.services.inspect(mock_service)
    labels = service_inspect["Spec"]["Labels"]
    scheduler_data = SchedulerData.parse_obj(
        json.loads(labels[DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL])
    )
    assert scheduler_data == mock_scheduler_data
