# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import Iterator

import pytest
from distributed import Client
from pydantic import AnyUrl
from pytest_simcore.helpers.utils_host import get_localhost_ip

from .helpers.utils_docker import get_service_published_port


@pytest.fixture
async def dask_scheduler_service(simcore_services_ready, monkeypatch) -> str:
    # the dask scheduler has a UI for the dashboard and a secondary port for the API
    # simcore_services fixture already ensure the dask-scheduler is up and running
    dask_scheduler_api_port = get_service_published_port(
        "dask-scheduler", target_ports=[8786]
    )
    # override the port
    monkeypatch.setenv("DASK_SCHEDULER_PORT", f"{dask_scheduler_api_port}")
    return AnyUrl.build(
        scheme="tls", host=get_localhost_ip(), port=dask_scheduler_api_port
    )


@pytest.fixture
def dask_client(dask_scheduler_service: str) -> Iterator[Client]:
    client = Client(dask_scheduler_service)
    yield client
    client.close()


@pytest.fixture
def dask_sidecar_service(dask_client: Client) -> None:
    dask_client.wait_for_workers(n_workers=1, timeout=30)
