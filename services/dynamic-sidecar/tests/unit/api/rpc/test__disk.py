# pylint:disable=protected-access
# pylint:disable=unused-argument
# ruff: noqa: SLF001


from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import disk
from simcore_service_dynamic_sidecar.core import reserved_space
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


async def test_free_reserved_disk_space(cleanup_reserved_disk_space: None, app: FastAPI, rpc_client: RabbitMQRPCClient):
    assert reserved_space._RESERVED_DISK_SPACE_NAME.exists()

    settings: ApplicationSettings = app.state.settings

    result = await disk.free_reserved_disk_space(
        rpc_client,
        node_id=settings.DY_SIDECAR_NODE_ID,
    )
    assert result is None

    assert not reserved_space._RESERVED_DISK_SPACE_NAME.exists()
