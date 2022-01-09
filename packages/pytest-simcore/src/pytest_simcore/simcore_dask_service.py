# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict, Iterator

import pytest
from distributed import Client

from .helpers.utils_docker import get_service_published_port


@pytest.fixture(scope="function")
async def dask_scheduler_service(simcore_services_ready, monkeypatch) -> Dict[str, Any]:
    # the dask scheduler has a UI for the dashboard and a secondary port for the API
    # simcore_services fixture already ensure the dask-scheduler is up and running
    dask_scheduler_api_port = get_service_published_port(
        "dask-scheduler", target_ports=[8786]
    )
    # override the port
    monkeypatch.setenv("DASK_SCHEDULER_PORT", f"{dask_scheduler_api_port}")
    return {"host": "127.0.0.1", "port": dask_scheduler_api_port}


@pytest.fixture(scope="function")
def dask_client(dask_scheduler_service: Dict[str, Any]) -> Iterator[Client]:

    client = Client(
        f"{dask_scheduler_service['host']}:{dask_scheduler_service['port']}"
    )
    yield client
    client.close()


@pytest.fixture(scope="function")
def dask_sidecar_service(dask_client: Client) -> None:
    dask_client.wait_for_workers(n_workers=1, timeout=30)
