# pylint:disable=unused-argument


from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import disk
from simcore_service_dynamic_sidecar.core.reserved_space import (
    _RESERVED_DISK_SPACE_NAME,
)
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


async def test_free_reserved_disk_space(
    cleanup_reserved_disk_space: None, app: FastAPI, rpc_client: RabbitMQRPCClient
):
    assert _RESERVED_DISK_SPACE_NAME.exists()

    settings: ApplicationSettings = app.state.settings

    result = await disk.free_reserved_disk_space(
        rpc_client,
        node_id=settings.DY_SIDECAR_NODE_ID,
    )
    assert result is None

    assert not _RESERVED_DISK_SPACE_NAME.exists()
