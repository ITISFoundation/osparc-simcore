# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import time

from distributed import Client, SpecCluster
from faker import Faker
from models_library.clusters import SimpleAuthentication
from pydantic import AnyUrl, SecretStr, parse_obj_as
from simcore_service_clusters_keeper.modules.dask import (
    is_gateway_busy,
    is_scheduler_busy,
    ping_scheduler,
)
from tenacity import retry
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


async def test_ping_scheduler_non_existing_scheduler(faker: Faker):
    assert await ping_scheduler(url=parse_obj_as(AnyUrl, faker.url())) is False


async def test_ping_scheduler(dask_spec_local_cluster: SpecCluster):
    assert ping_scheduler(
        parse_obj_as(AnyUrl, dask_spec_local_cluster.scheduler_address)
    )


@retry(
    wait=wait_fixed(1),
    stop=stop_after_delay(30),
    retry=retry_if_exception_type(AssertionError),
)
async def _assert_scheduler_is_busy(
    url: AnyUrl, user: str, password: SecretStr, *, busy: bool
) -> None:
    print(f"--> waiting for gateway to become {busy=}")
    assert await is_scheduler_busy(url=url) is busy
    print(f"scheduler is now {busy=}")


async def test_is_gateway_busy(
    dask_spec_local_cluster: SpecCluster,
    dask_gateway_cluster: GatewayCluster,
    dask_gateway_cluster_client: Client,
):
    # nothing runs right now
    assert dask_gateway_cluster.gateway.auth
    assert isinstance(dask_gateway_cluster.gateway.auth, auth.BasicAuth)
    assert (
        await is_gateway_busy(
            url=parse_obj_as(AnyUrl, local_dask_gateway_server.address),
            gateway_auth=SimpleAuthentication(
                username=dask_gateway_cluster.gateway.auth.username,
                password=SecretStr(local_dask_gateway_server.password),
            ),
        )
        is False
    )
    await dask_gateway_cluster.scale(1)
    assert (
        await is_gateway_busy(
            url=parse_obj_as(AnyUrl, local_dask_gateway_server.address),
            gateway_auth=SimpleAuthentication(
                username=dask_gateway_cluster.gateway.auth.username,
                password=SecretStr(local_dask_gateway_server.password),
            ),
        )
        is False
    )
    _SLEEP_TIME = 5

    def _some_long_running_fct(sleep_time: int) -> str:
        time.sleep(sleep_time)
        return f"I slept for {sleep_time} seconds"

    future = dask_gateway_cluster_client.submit(_some_long_running_fct, _SLEEP_TIME)

    await _assert_scheduler_is_busy(
        url=parse_obj_as(AnyUrl, local_dask_gateway_server.address),
        user=f"{dask_gateway_cluster.gateway.auth.username}",
        password=SecretStr(local_dask_gateway_server.password),
        busy=True,
    )

    result = await future.result(timeout=2 * _SLEEP_TIME)  # type: ignore
    assert "seconds" in result
