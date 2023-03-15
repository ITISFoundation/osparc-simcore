# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import AsyncIterator

import aiohttp
import dask_gateway
import pytest
from faker import Faker
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_plugins = ["pytest_simcore.repository_paths", "pytest_simcore.docker_swarm"]


@pytest.fixture
async def aiohttp_client() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
def minimal_config(monkeypatch):
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("GATEWAY_SERVER_ONE_WORKER_PER_NODE", "False")


@pytest.fixture(scope="session")
def dask_gateway_entrypoint() -> str:
    return f"http://{get_localhost_ip()}:8000"


@pytest.fixture(scope="session")
def dask_gateway_password() -> str:
    return "asdf"


@pytest.fixture
async def dask_gateway_stack_deployed_services(
    minimal_config,
    package_dir: Path,
    docker_swarm,
    aiohttp_client: aiohttp.ClientSession,
    dask_gateway_entrypoint: str,
):
    print("--> Deploying osparc-dask-gateway stack...")
    process = await asyncio.create_subprocess_exec(
        "make",
        "up-prod",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=package_dir,
    )
    stdout, stderr = await process.communicate()
    assert (
        process.returncode == 0
    ), f"Unexpected error while deploying stack:\nstdout:{stdout.decode()}\n\nstderr:{stderr.decode()}"
    print(f"{stdout}")
    print("--> osparc-dask-gateway stack deployed.")
    healtcheck_endpoint = f"{dask_gateway_entrypoint}/api/health"
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)
    ):
        with attempt:
            print(
                f"--> Connecting to {healtcheck_endpoint}, "
                f"attempt {attempt.retry_state.attempt_number}...",
            )
            response = await aiohttp_client.get(healtcheck_endpoint)
            response.raise_for_status()
        print(
            f"--> Connection to gateway server succeeded."
            f" [{json.dumps(attempt.retry_state.retry_object.statistics)}]",
        )

    yield
    print("<-- Stopping osparc-dask-gateway stack...")
    process = await asyncio.create_subprocess_exec(
        "make",
        "down",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=package_dir,
    )
    stdout, stderr = await process.communicate()
    assert (
        process.returncode == 0
    ), f"Unexpected error while deploying stack:\nstdout:{stdout.decode()}\n\n{stderr.decode()}"
    print(f"{stdout}")
    print("<-- osparc-dask-gateway stack stopped.")


async def test_deployment(
    dask_gateway_stack_deployed_services,
    dask_gateway_entrypoint: str,
    faker: Faker,
    dask_gateway_password: str,
):
    gateway = dask_gateway.Gateway(
        address=dask_gateway_entrypoint,
        auth=dask_gateway.BasicAuth(faker.pystr(), dask_gateway_password),
    )

    with gateway.new_cluster() as cluster:
        _NUM_WORKERS = 2
        cluster.scale(
            _NUM_WORKERS
        )  # when returning we are in the process of creating the workers

        # now wait until we get the workers
        workers = None
        async for attempt in AsyncRetrying(
            reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)
        ):
            with attempt:
                print(
                    f"--> Waiting to have {_NUM_WORKERS} running,"
                    f" attempt {attempt.retry_state.attempt_number}...",
                )
                assert "workers" in cluster.scheduler_info
                assert len(cluster.scheduler_info["workers"]) == _NUM_WORKERS
                workers = deepcopy(cluster.scheduler_info["workers"])
                print(
                    f"!-- {_NUM_WORKERS} are running,"
                    f" [{json.dumps(attempt.retry_state.retry_object.statistics)}]",
                )

        # now check all this is stable
        _SECONDS_STABLE = 6
        for n in range(_SECONDS_STABLE):
            # NOTE: the scheduler_info gets auto-udpated by the dask-gateway internals
            assert workers == cluster.scheduler_info["workers"]
            await asyncio.sleep(1)
            print(f"!-- {_NUM_WORKERS} stable for {n} seconds")

        # send some work
        def square(x):
            return x**2

        def neg(x):
            return -x

        with cluster.get_client() as client:
            square_of_2 = client.submit(square, 2)
            assert square_of_2.result(timeout=10) == 4
            assert not square_of_2.exception(timeout=10)

            # now send some more stuff just for the fun
            A = client.map(square, range(10))
            B = client.map(neg, A)

            total = client.submit(sum, B)
            print("computation completed", total.result(timeout=120))
