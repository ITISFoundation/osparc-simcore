# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import os
from collections.abc import Callable, Iterable
from copy import deepcopy

import aiohttp
import pytest
import tenacity
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from servicelib.minio_utils import ServiceRetryPolicyUponInitialization
from yarl import URL

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.storage import replace_storage_endpoint
from .helpers.typing_env import EnvVarsDict


@pytest.fixture(scope="module")
def storage_endpoint(
    docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict
) -> Iterable[URL]:
    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_storage" in docker_stack["services"]

    default_port = int(env_vars_for_docker_compose["STORAGE_ENDPOINT"].split(":")[1])
    endpoint = (
        f"{get_localhost_ip()}:{get_service_published_port('storage', default_port)}"
    )

    # nodeports takes its configuration from env variables
    old_environ = deepcopy(os.environ)
    os.environ["STORAGE_ENDPOINT"] = endpoint

    yield URL(f"http://{endpoint}")

    # restore environ
    os.environ = old_environ


@pytest.fixture()
async def storage_service(
    mocker: MockerFixture, storage_endpoint: URL, docker_stack: dict
) -> URL:
    await wait_till_storage_responsive(storage_endpoint)

    # NOTE: Mock to ensure container IP agrees with host IP when testing
    assert storage_endpoint.host is not None
    assert storage_endpoint.port is not None
    mocker.patch(
        "simcore_sdk.node_ports_common._filemanager._get_https_link_if_storage_secure",
        replace_storage_endpoint(storage_endpoint.host, storage_endpoint.port),
    )

    return storage_endpoint


# TODO: this can be used by ANY of the simcore services!
@tenacity.retry(**ServiceRetryPolicyUponInitialization().kwargs)
async def wait_till_storage_responsive(storage_endpoint: URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(storage_endpoint.with_path("/v0/")) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "data" in data
            assert data["data"] is not None


@pytest.fixture
def create_simcore_file_id() -> Callable[[ProjectID, NodeID, str], SimcoreS3FileID]:
    def _creator(
        project_id: ProjectID, node_id: NodeID, file_name: str
    ) -> SimcoreS3FileID:
        return TypeAdapter(SimcoreS3FileID).validate_python(
            f"{project_id}/{node_id}/{file_name}"
        )

    return _creator
