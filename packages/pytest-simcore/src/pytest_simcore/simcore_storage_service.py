# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import os
from copy import deepcopy
from typing import Dict

import aiohttp
import pytest
import tenacity
from s3wrapper.s3_client import S3Client
from servicelib.minio_utils import MinioRetryPolicyUponInitialization
from yarl import URL

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def storage_endpoint(docker_stack: Dict, devel_environ: Dict) -> URL:
    assert "simcore_storage" in docker_stack["services"]
    default_port = devel_environ["STORAGE_ENDPOINT"].split(":")[1]
    endpoint = f"127.0.0.1:{get_service_published_port('storage', default_port)}"

    # nodeports takes its configuration from env variables
    old_environ = deepcopy(os.environ)
    os.environ["STORAGE_ENDPOINT"] = endpoint

    yield URL(f"http://{endpoint}")

    # restore environ
    os.environ = old_environ


@pytest.fixture(scope="function")
async def storage_service(
    minio_service: S3Client, storage_endpoint: URL, docker_stack: Dict
) -> URL:
    await wait_till_storage_responsive(storage_endpoint)

    yield storage_endpoint


# HELPERS --

# TODO: this can be used by ANY of the simcore services!
@tenacity.retry(**MinioRetryPolicyUponInitialization().kwargs)
async def wait_till_storage_responsive(storage_endpoint: URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(storage_endpoint.with_path("/v0/")) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "data" in data
            assert data["data"] is not None
