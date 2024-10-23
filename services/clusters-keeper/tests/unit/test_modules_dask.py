# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import time

import distributed
import pytest
from distributed import SpecCluster
from faker import Faker
from models_library.clusters import (
    InternalClusterAuthentication,
    NoAuthentication,
    TLSAuthentication,
)
from pydantic import AnyUrl, TypeAdapter
from simcore_service_clusters_keeper.modules.dask import (
    is_scheduler_busy,
    ping_scheduler,
)
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_authentication_types = [
    NoAuthentication(),
    TLSAuthentication.model_construct(
        **TLSAuthentication.model_config["json_schema_extra"]["examples"][0]
    ),
]


@pytest.mark.parametrize(
    "authentication", _authentication_types, ids=lambda p: f"authentication-{p.type}"
)
async def test_ping_scheduler_non_existing_scheduler(
    faker: Faker, authentication: InternalClusterAuthentication
):
    assert (
        await ping_scheduler(
            TypeAdapter(AnyUrl).validate_python(f"tcp://{faker.ipv4()}:{faker.port_number()}"),
            authentication,
        )
        is False
    )


async def test_ping_scheduler(dask_spec_local_cluster: SpecCluster):
    assert (
        await ping_scheduler(
            TypeAdapter(AnyUrl).validate_python(dask_spec_local_cluster.scheduler_address),
            NoAuthentication(),
        )
        is True
    )


@retry(
    wait=wait_fixed(1),
    stop=stop_after_delay(30),
    retry=retry_if_exception_type(AssertionError),
)
async def _assert_scheduler_is_busy(url: AnyUrl, *, busy: bool) -> None:
    print(f"--> waiting for osparc-dask-scheduler to become {busy=}")
    assert await is_scheduler_busy(url, NoAuthentication()) is busy
    print(f"scheduler is now {busy=}")


async def test_is_scheduler_busy(
    dask_spec_local_cluster: distributed.SpecCluster,
    dask_spec_cluster_client: distributed.Client,
):
    # nothing runs right now
    scheduler_address = TypeAdapter(AnyUrl).validate_python(dask_spec_local_cluster.scheduler_address)
    assert await is_scheduler_busy(scheduler_address, NoAuthentication()) is False
    _SLEEP_TIME = 5

    def _some_long_running_fct(sleep_time: int) -> str:
        time.sleep(sleep_time)
        return f"I slept for {sleep_time} seconds"

    future = dask_spec_cluster_client.submit(_some_long_running_fct, _SLEEP_TIME)

    await _assert_scheduler_is_busy(
        url=scheduler_address,
        busy=True,
    )

    result = await future.result(timeout=2 * _SLEEP_TIME)
    assert "seconds" in result
