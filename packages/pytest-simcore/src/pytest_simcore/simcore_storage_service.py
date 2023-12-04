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
from pydantic import parse_obj_as
from servicelib.minio_utils import ServiceRetryPolicyUponInitialization
from yarl import URL

from .helpers.utils_docker import get_service_published_port
from .helpers.utils_host import get_localhost_ip


@pytest.fixture(scope="module")
def storage_endpoint(docker_stack: dict, testing_environ_vars: dict) -> Iterable[URL]:
    prefix = testing_environ_vars["SWARM_STACK_NAME"]
    assert f"{prefix}_storage" in docker_stack["services"]

    default_port = testing_environ_vars["STORAGE_ENDPOINT"].split(":")[1]
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
async def storage_service(storage_endpoint: URL, docker_stack: dict) -> URL:
    await wait_till_storage_responsive(storage_endpoint)

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
        return parse_obj_as(SimcoreS3FileID, f"{project_id}/{node_id}/{file_name}")

    return _creator
