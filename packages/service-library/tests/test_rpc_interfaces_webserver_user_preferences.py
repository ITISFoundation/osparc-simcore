import pytest
from models_library.rabbitmq_basic_types import RPCNamespace
from models_library.shared_user_preferences import InvoiceEmailRecipientsFrontendUserPreference
from models_library.users import UserID
from pydantic import ValidationError
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import UserPreferencesRpcApi


async def test_get_frontend_user_preference_returns_validated_payload(mocker: MockerFixture):
    user_id = UserID(42)
    product_name = "osparc"
    preference_name = InvoiceEmailRecipientsFrontendUserPreference.get_preference_name()
    payload = InvoiceEmailRecipientsFrontendUserPreference(value=["billing@example.com"]).model_dump(mode="json")
    rpc_client = mocker.Mock(spec=RabbitMQRPCClient)
    rpc_client.request = mocker.AsyncMock(return_value=payload)
    api = UserPreferencesRpcApi(rpc_client, RPCNamespace("test"))

    preference = await api.get_frontend_user_preference(
        user_id=user_id,
        product_name=product_name,
        preference_class=InvoiceEmailRecipientsFrontendUserPreference,
    )

    assert preference is not None
    assert preference.value == ["billing@example.com"]
    rpc_client.request.assert_awaited_once_with(
        RPCNamespace("test"),
        "get_frontend_user_preference",
        product_name=product_name,
        user_id=user_id,
        preference_name=preference_name,
    )


async def test_get_frontend_user_preference_returns_none_when_unset(mocker: MockerFixture):
    rpc_client = mocker.Mock(spec=RabbitMQRPCClient)
    rpc_client.request = mocker.AsyncMock(return_value=None)
    api = UserPreferencesRpcApi(rpc_client, RPCNamespace("test"))

    preference = await api.get_frontend_user_preference(
        user_id=UserID(42),
        product_name="osparc",
        preference_class=InvoiceEmailRecipientsFrontendUserPreference,
    )

    assert preference is None


async def test_get_frontend_user_preference_rejects_invalid_typed_payload(mocker: MockerFixture):
    rpc_client = mocker.Mock(spec=RabbitMQRPCClient)
    rpc_client.request = mocker.AsyncMock(
        return_value={
            "preference_type": "FRONTEND",
            "preference_identifier": "invoiceEmailRecipients",
            "value": ["not-an-email"],
        }
    )
    api = UserPreferencesRpcApi(rpc_client, RPCNamespace("test"))

    with pytest.raises(ValidationError):
        await api.get_frontend_user_preference(
            user_id=UserID(42),
            product_name="osparc",
            preference_class=InvoiceEmailRecipientsFrontendUserPreference,
        )
