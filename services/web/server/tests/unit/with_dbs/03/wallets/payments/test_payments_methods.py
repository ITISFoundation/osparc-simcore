# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.wallets import (
    GetWalletAutoRecharge,
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInit,
    WalletGet,
)
from models_library.wallets import WalletID
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_service_webserver.payments._methods_api import (
    _ack_creation_of_wallet_payment_method,
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
    await _ack_creation_of_wallet_payment_method(
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

    # Get -> NOT FOUND
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    data, _ = await assert_status(response, web.HTTPNotFound)

    # List -> empty
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


async def _add_payment_method(
    client: TestClient, wallet_id: WalletID
) -> PaymentMethodID:
    assert client.app
    response = await client.post(
        f"/v0/wallets/{wallet_id}/payments-methods:init",
    )
    data, error = await assert_status(response, web.HTTPAccepted)
    assert error is None
    inited = PaymentMethodInit.parse_obj(data)
    await _ack_creation_of_wallet_payment_method(
        client.app,
        payment_method_id=inited.payment_method_id,
        completion_state=InitPromptAckFlowState.SUCCESS,
        message="ACKED by test_add_payment_method_worfklow",
    )

    return inited.payment_method_id


@pytest.mark.acceptance_test(
    "Part of https://github.com/ITISFoundation/osparc-simcore/issues/4751"
)
async def test_wallet_autorecharge(
    client: TestClient,
    logged_user_wallet: WalletGet,
):
    wallet = logged_user_wallet

    # get default
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/auto-recharge")

    data, _ = await assert_status(response, web.HTTPOk)
    default_auto_recharge = GetWalletAutoRecharge(**data)
    assert default_auto_recharge.enabled is False
    assert default_auto_recharge.top_up_countdown is None
    assert default_auto_recharge.payment_method_id is None

    # A wallet with a payment method
    older_payment_method_id = await _add_payment_method(
        client, wallet_id=wallet.wallet_id
    )
    payment_method_id = await _add_payment_method(client, wallet_id=wallet.wallet_id)

    # get default again
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/auto-recharge")
    data, _ = await assert_status(response, web.HTTPOk)
    default_auto_recharge = GetWalletAutoRecharge(**data)
    assert default_auto_recharge.enabled is False
    assert default_auto_recharge.top_up_countdown is None
    assert default_auto_recharge.payment_method_id == payment_method_id

    # Activate auto-rechange
    response = await client.put(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
        json={
            "paymentMethodId": payment_method_id,
            "minBalanceInUsd": 0.0,
            "topUpAmountInUsd": 100.0,  # $
            "topUpCountdown": 3,
            "enabled": True,
        },
    )
    data, _ = await assert_status(response, web.HTTPOk)
    updated_auto_recharge = GetWalletAutoRecharge.parse_obj(data)
    assert updated_auto_recharge == GetWalletAutoRecharge(
        payment_method_id=payment_method_id,
        min_balance_in_usd=0.0,
        top_up_amount_in_usd=100.0,  # $
        top_up_countdown=3,
        enabled=True,
    )

    # get
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
    )
    data, _ = await assert_status(response, web.HTTPOk)
    assert updated_auto_recharge == GetWalletAutoRecharge.parse_obj(data)

    # payment-methods.auto_recharge
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-methods")
    data, _ = await assert_status(response, web.HTTPOk)
    wallet_payment_methods = parse_obj_as(list[PaymentMethodGet], data)

    for payment_method in wallet_payment_methods:
        assert payment_method.auto_recharge == (payment_method.idr == payment_method_id)

    assert {pm.idr for pm in wallet_payment_methods} == {
        payment_method_id,
        older_payment_method_id,
    }
    assert sum(pm.auto_recharge for pm in wallet_payment_methods) == 1


async def test_delete_primary_payment_method_in_autorecharge(
    client: TestClient,
    logged_user_wallet: WalletGet,
):
    wallet = logged_user_wallet
    payment_method_id = await _add_payment_method(client, wallet_id=wallet.wallet_id)

    # attach this payment method to the wallet's auto-recharge
    response = await client.put(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
        json={
            "paymentMethodId": payment_method_id,
            "minBalanceInUsd": 0.0,
            "topUpAmountInUsd": 100.0,  # $
            "topUpCountdown": 3,
            "enabled": True,
        },
    )
    data, _ = await assert_status(response, web.HTTPOk)
    auto_recharge = GetWalletAutoRecharge.parse_obj(data)
    assert auto_recharge.enabled is True
    assert auto_recharge.payment_method_id == payment_method_id

    # delete payment-method
    response = await client.delete(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{payment_method_id}"
    )
    await assert_status(response, web.HTTPNoContent)

    # get -> has no payment-method
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
    )
    data, _ = await assert_status(response, web.HTTPOk)
    auto_recharge_after_delete = GetWalletAutoRecharge.parse_obj(data)

    assert auto_recharge_after_delete.payment_method_id is None
    assert auto_recharge_after_delete.enabled is False

    # Having a new payment method
    new_payment_method_id = await _add_payment_method(
        client, wallet_id=wallet.wallet_id
    )
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
    )
    data, _ = await assert_status(response, web.HTTPOk)
    auto_recharge = GetWalletAutoRecharge.parse_obj(data)
    assert auto_recharge.payment_method_id == new_payment_method_id
    assert auto_recharge.enabled is False
