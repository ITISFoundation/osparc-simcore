# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    GetWalletAutoRecharge,
    PaymentMethodGet,
    PaymentMethodID,
    PaymentMethodInitiated,
    PaymentTransaction,
    WalletGet,
    WalletPaymentInitiated,
)
from models_library.rest_pagination import Page
from models_library.wallets import WalletID
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import status
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_service_webserver.payments._methods_api import (
    _ack_creation_of_wallet_payment_method,
)
from simcore_service_webserver.payments.settings import PaymentsSettings
from simcore_service_webserver.payments.settings import (
    get_plugin_settings as get_payments_plugin_settings,
)


@pytest.mark.acceptance_test(
    "Part of https://github.com/ITISFoundation/osparc-simcore/issues/4751"
)
async def test_payment_method_worfklow(
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
    mock_rpc_payments_service_api: dict[str, MagicMock],
):
    # preamble
    assert client.app

    settings: PaymentsSettings = get_payments_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_message_to_user",
        autospec=True,
    )

    wallet = logged_user_wallet

    # init Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods:init",
    )
    data, error = await assert_status(response, status.HTTP_202_ACCEPTED)
    assert error is None
    inited = PaymentMethodInitiated.parse_obj(data)

    assert inited.payment_method_id
    assert inited.payment_method_form_url.query
    assert inited.payment_method_form_url.query.endswith(inited.payment_method_id)
    assert mock_rpc_payments_service_api["init_creation_of_payment_method"].called

    # Get: if I try to get the payment method here, it should fail since the flow is NOT acked!
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    await assert_status(response, status.HTTP_404_NOT_FOUND)
    assert mock_rpc_payments_service_api["get_payment_method"].called

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
    data, _ = await assert_status(response, status.HTTP_200_OK)
    payment_method = PaymentMethodGet(**data)
    assert payment_method.idr == inited.payment_method_id

    # List
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-methods")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert mock_rpc_payments_service_api["list_payment_methods"].called

    wallet_payments_methods = parse_obj_as(list[PaymentMethodGet], data)
    assert wallet_payments_methods == [payment_method]

    # Delete
    response = await client.delete(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    await assert_status(response, status.HTTP_204_NO_CONTENT)
    assert mock_rpc_payments_service_api["delete_payment_method"].called

    # Get -> NOT FOUND
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    data, _ = await assert_status(response, status.HTTP_404_NOT_FOUND)
    assert mock_rpc_payments_service_api["get_payment_method"].call_count == 3

    # List -> empty
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-methods")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert not data
    assert mock_rpc_payments_service_api["list_payment_methods"].call_count == 2


async def test_init_and_cancel_payment_method(
    client: TestClient,
    logged_user_wallet: WalletGet,
    mock_rpc_payments_service_api: dict[str, MagicMock],
):
    wallet = logged_user_wallet

    # init Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods:init",
    )
    data, error = await assert_status(response, status.HTTP_202_ACCEPTED)
    assert error is None
    inited = PaymentMethodInitiated.parse_obj(data)

    # cancel Create
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}:cancel",
    )
    await assert_status(response, status.HTTP_204_NO_CONTENT)
    assert mock_rpc_payments_service_api["cancel_creation_of_payment_method"].called

    # Get -> not found
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{inited.payment_method_id}"
    )
    await assert_status(response, status.HTTP_404_NOT_FOUND)


async def _add_payment_method(
    client: TestClient, wallet_id: WalletID
) -> PaymentMethodID:
    assert client.app
    response = await client.post(
        f"/v0/wallets/{wallet_id}/payments-methods:init",
    )
    data, error = await assert_status(response, status.HTTP_202_ACCEPTED)
    assert error is None
    inited = PaymentMethodInitiated.parse_obj(data)
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
@pytest.mark.parametrize(
    "amount_usd,expected_status",
    [
        (1, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (123.45, status.HTTP_200_OK),
    ],
)
async def test_wallet_autorecharge(
    latest_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mock_rpc_payments_service_api: dict[str, MagicMock],
    amount_usd: int,
    expected_status: int,
):
    assert client.app
    assert latest_osparc_price > 0, "current product should be billable"

    settings = get_payments_plugin_settings(client.app)
    wallet = logged_user_wallet

    # get default
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/auto-recharge")

    data, _ = await assert_status(response, status.HTTP_200_OK)
    default_auto_recharge = GetWalletAutoRecharge(**data)
    assert default_auto_recharge.enabled is False
    assert default_auto_recharge.payment_method_id is None
    assert (
        default_auto_recharge.min_balance_in_credits
        == settings.PAYMENTS_AUTORECHARGE_MIN_BALANCE_IN_CREDITS
    )
    assert (
        default_auto_recharge.top_up_amount_in_usd
        == settings.PAYMENTS_AUTORECHARGE_DEFAULT_TOP_UP_AMOUNT
    )
    assert (
        default_auto_recharge.monthly_limit_in_usd
        == settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT
    )

    # A wallet with a payment method
    older_payment_method_id = await _add_payment_method(
        client, wallet_id=wallet.wallet_id
    )
    payment_method_id = await _add_payment_method(client, wallet_id=wallet.wallet_id)

    # get default again
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/auto-recharge")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    default_auto_recharge = GetWalletAutoRecharge(**data)
    assert default_auto_recharge.enabled is False
    assert (
        default_auto_recharge.monthly_limit_in_usd
        == settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT
    )
    assert default_auto_recharge.payment_method_id == payment_method_id

    # Activate auto-rechange
    response = await client.put(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
        json={
            "paymentMethodId": payment_method_id,
            "topUpAmountInUsd": amount_usd,  # $
            "monthlyLimitInUsd": 6543.21,  # $
            "enabled": True,
        },
    )
    data, error = await assert_status(response, expected_status)
    if not error:
        updated_auto_recharge = GetWalletAutoRecharge.parse_obj(data)
        assert updated_auto_recharge == GetWalletAutoRecharge(
            payment_method_id=payment_method_id,
            min_balance_in_credits=settings.PAYMENTS_AUTORECHARGE_MIN_BALANCE_IN_CREDITS,
            top_up_amount_in_usd=amount_usd,  # $
            monthly_limit_in_usd=6543.21,  # $
            enabled=True,
        )

        # get
        response = await client.get(
            f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
        )
        data, _ = await assert_status(response, status.HTTP_200_OK)
        assert updated_auto_recharge == GetWalletAutoRecharge.parse_obj(data)

        # payment-methods.auto_recharge
        response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-methods")
        data, _ = await assert_status(response, status.HTTP_200_OK)
        wallet_payment_methods = parse_obj_as(list[PaymentMethodGet], data)

        for payment_method in wallet_payment_methods:
            assert payment_method.auto_recharge == (
                payment_method.idr == payment_method_id
            )

        assert {pm.idr for pm in wallet_payment_methods} == {
            payment_method_id,
            older_payment_method_id,
        }
        assert sum(pm.auto_recharge for pm in wallet_payment_methods) == 1


async def test_delete_primary_payment_method_in_autorecharge(
    client: TestClient,
    logged_user_wallet: WalletGet,
    latest_osparc_price: Decimal,
    mock_rpc_payments_service_api: dict[str, MagicMock],
):
    assert client.app
    assert latest_osparc_price > 0, "current product should be billable"

    wallet = logged_user_wallet
    payment_method_id = await _add_payment_method(client, wallet_id=wallet.wallet_id)

    # attach this payment method to the wallet's auto-recharge
    response = await client.put(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
        json={
            "paymentMethodId": payment_method_id,
            "topUpAmountInUsd": 100.0,
            "monthlyLimitInUsd": 123,
            "enabled": True,
        },
    )
    data, _ = await assert_status(response, status.HTTP_200_OK)
    auto_recharge = GetWalletAutoRecharge.parse_obj(data)
    assert auto_recharge.enabled is True
    assert auto_recharge.payment_method_id == payment_method_id
    assert auto_recharge.monthly_limit_in_usd == 123

    # delete payment-method
    response = await client.delete(
        f"/v0/wallets/{wallet.wallet_id}/payments-methods/{payment_method_id}"
    )
    await assert_status(response, status.HTTP_204_NO_CONTENT)

    # get -> has no payment-method
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/auto-recharge",
    )
    data, _ = await assert_status(response, status.HTTP_200_OK)
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
    data, _ = await assert_status(response, status.HTTP_200_OK)
    auto_recharge = GetWalletAutoRecharge.parse_obj(data)
    assert auto_recharge.payment_method_id == new_payment_method_id
    assert auto_recharge.enabled is False


@pytest.fixture
async def wallet_payment_method_id(
    client: TestClient,
    logged_user_wallet: WalletGet,
    mock_rpc_payments_service_api: dict[str, MagicMock],
):
    return await _add_payment_method(client, wallet_id=logged_user_wallet.wallet_id)


@pytest.mark.parametrize(
    "amount_usd,expected_status",
    [
        (1, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (26, status.HTTP_202_ACCEPTED),
    ],
)
async def test_one_time_payment_with_payment_method(
    latest_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mock_rpc_payments_service_api: dict[str, MagicMock],
    wallet_payment_method_id: PaymentMethodID,
    mocker: MockerFixture,
    faker: Faker,
    amount_usd: int,
    expected_status: int,
    setup_user_pre_registration_details_db: None,
):
    assert client.app
    assert latest_osparc_price > 0, "current product should be billable"

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_message_to_user",
        autospec=True,
    )
    mock_rut_add_credits_to_wallet = mocker.patch(
        "simcore_service_webserver.payments._onetime_api.add_credits_to_wallet",
        autospec=True,
    )

    assert (
        client.app.router["pay_with_payment_method"]
        .url_for(
            wallet_id=f"{logged_user_wallet.wallet_id}",
            payment_method_id=wallet_payment_method_id,
        )
        .path
        == f"/v0/wallets/{logged_user_wallet.wallet_id}/payments-methods/{wallet_payment_method_id}:pay"
    )

    # TEST add payment to wallet
    response = await client.post(
        f"/v0/wallets/{logged_user_wallet.wallet_id}/payments-methods/{wallet_payment_method_id}:pay",
        json={
            "priceDollars": amount_usd,
        },
    )
    data, error = await assert_status(response, expected_status)
    if not error:
        payment = WalletPaymentInitiated.parse_obj(data)
        assert mock_rpc_payments_service_api["pay_with_payment_method"].called

        assert payment.payment_id
        assert payment.payment_form_url is None

        # check notification to RUT (fake)
        assert mock_rut_add_credits_to_wallet.called
        mock_rut_add_credits_to_wallet.assert_called_once()

        # check notification after response
        await asyncio.sleep(0.1)
        assert send_message.called
        send_message.assert_called_once()

        # list all payment transactions in all my wallets
        response = await client.get("/v0/wallets/-/payments")
        data, error = await assert_status(response, status.HTTP_200_OK)

        page = parse_obj_as(Page[PaymentTransaction], data)

        assert page.data
        assert page.meta.total == 1
        assert page.meta.offset == 0

        transaction = page.data[0]
        assert transaction.payment_id == payment.payment_id

        # payment was completed successfully
        assert transaction.completed_at is not None
        assert transaction.created_at < transaction.completed_at
        assert transaction.invoice_url is not None
