# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest import mock
from uuid import uuid4

from models_library.celery import (
    GroupStatus,
    OwnerMetadata,
    ProgressReport,
    TaskState,
    TaskStatus,
)
from models_library.notifications.rpc import (
    GetMessageStatusRequest,
    GetMessageStatusResponse,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.notifications import get_message_status


class _ServiceLocalOwnerMetadata(OwnerMetadata):
    """A service-side subclass, like the web-server's WebServerOwnerMetadata.

    It is importable on the caller side only: RPC arguments are pickled by
    reference, so such an instance must never reach the wire.
    """

    user_id: int
    product_name: str
    owner: str = "webserver"


async def test_get_message_status_sends_the_shared_owner_metadata_model():
    owner_metadata = _ServiceLocalOwnerMetadata(user_id=42, product_name="osparc")

    response = GetMessageStatusResponse(
        status=TaskStatus(
            task_uuid=uuid4(),
            task_state=TaskState.SUCCESS,
            progress_report=ProgressReport(actual_value=1.0),
        )
    )
    client = mock.create_autospec(RabbitMQRPCClient, instance=True)
    client.request.return_value = response

    result = await get_message_status(
        client,
        owner_metadata=owner_metadata,
        task_or_group_uuid=uuid4(),
    )

    assert result is response
    request: GetMessageStatusRequest = client.request.await_args.kwargs["request"]
    sent = request.owner_metadata
    assert type(sent) is OwnerMetadata
    assert sent.model_dump() == owner_metadata.model_dump()


async def test_get_message_status_accepts_the_shared_model_unchanged():
    owner_metadata = OwnerMetadata.model_validate({"owner": "webserver", "user_id": 42, "product_name": "osparc"})

    response = GetMessageStatusResponse(
        status=GroupStatus(
            group_uuid=uuid4(),
            task_uuids=[uuid4()],
            completed_count=1,
            total_count=1,
            is_done=True,
            is_successful=True,
            progress_report=ProgressReport(actual_value=1.0),
        )
    )
    client = mock.create_autospec(RabbitMQRPCClient, instance=True)
    client.request.return_value = response

    await get_message_status(
        client,
        owner_metadata=owner_metadata,
        task_or_group_uuid=uuid4(),
    )

    request: GetMessageStatusRequest = client.request.await_args.kwargs["request"]
    assert request.owner_metadata.model_dump() == owner_metadata.model_dump()
