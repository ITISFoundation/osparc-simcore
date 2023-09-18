# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodGet,
    PaymentMethodInit,
    WalletGet,
)
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_service_webserver.payments._methods_api import (
    _complete_create_of_wallet_payment_method,
)
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)


@pytest.mark.acceptance_test(
    "Part of https://github.com/ITISFoundation/osparc-simcore/issues/4751"
)
async def test_payment_method_worfklow(
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
):
    # preamble
    assert client.app
    settings: PaymentsSettings = get_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_messages", autospec=True
    )

    wallet = logged_user_wallet

    # init Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods:init",
    )
    data, error = await assert_status(response, web.HTTPAccepted)
    assert error is None
    inited = PaymentMethodInit.parse_obj(data)

    assert inited.payment_method_id
    assert inited.payment_method_form_url.query
    assert inited.payment_method_form_url.query.endswith(inited.payment_method_id)

    # Get: if I try to get the payment method here, it should fail since the flow is NOT acked!
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    await assert_status(response, web.HTTPNotFound)

    # Ack
    await _complete_create_of_wallet_payment_method(
        client.app,
        payment_method_id=inited.payment_method_id,
        completion_state=InitPromptAckFlowState.SUCCESS,
        message="ACKED by test_add_payment_method_worfklow",
    )

    assert send_message.called
    send_message.assert_called_once()

    # Get
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    data, _ = await assert_status(response, web.HTTPOk)
    payment_method = PaymentMethodGet(**data)
    assert payment_method.idr == inited.payment_method_id

    # List
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-methods")
    data, _ = await assert_status(response, web.HTTPOk)

    wallet_payments_methods = parse_obj_as(list[PaymentMethodGet], data)
    assert wallet_payments_methods == [payment_method]

    # Delete
    response = await client.delete(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    await assert_status(response, web.HTTPNoContent)

    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-methods")
    data, _ = await assert_status(response, web.HTTPOk)
    assert not data


async def test_init_and_cancel_payment_method(
    client: TestClient,
    logged_user_wallet: WalletGet,
):
    wallet = logged_user_wallet

    # init Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods:init",
    )
    data, error = await assert_status(response, web.HTTPAccepted)
    assert error is None
    inited = PaymentMethodInit.parse_obj(data)

    # cancel Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}:cancel",
    )
    await assert_status(response, web.HTTPNoContent)

    # Get -> not found
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    await assert_status(response, web.HTTPNotFound)
