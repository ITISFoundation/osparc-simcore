# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from typing import Dict

import aiohttp
import pytest
import tenacity
from yarl import URL

from s3wrapper.s3_client import S3Client
from servicelib.minio_utils import MinioRetryPolicyUponInitialization
from utils_docker import get_service_published_port


@pytest.fixture(scope="module")
def storage_endpoint(docker_stack: Dict, devel_environ: Dict) -> URL:
    assert "simcore_storage" in docker_stack["services"]
    default_port = devel_environ["STORAGE_ENDPOINT"].split(":")[1]
    endpoint = f"127.0.0.1:{get_service_published_port('storage', default_port)}"

    # nodeports takes its configuration from env variables
    os.environ[f"STORAGE_ENDPOINT"] = endpoint

    return URL(f"http://{endpoint}")


@pytest.fixture(scope="function")
async def storage_service(
    minio_service: S3Client, storage_endpoint: URL, docker_stack: Dict
) -> URL:
    assert await wait_till_storage_responsive(storage_endpoint)

    yield storage_endpoint


@tenacity.retry(**MinioRetryPolicyUponInitialization().kwargs)
async def wait_till_storage_responsive(storage_endpoint: URL) -> bool:
    """Check if something responds to ``url`` """
    async with aiohttp.ClientSession() as session:
        async with session.get(storage_endpoint.with_path("/v0/")) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "data" in data
            assert "status" in data["data"]
            assert data["data"]["status"] == "SERVICE_RUNNING"
    return True
