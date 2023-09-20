# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from decimal import Decimal
from typing import Any, TypeAlias

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    PaymentTransaction,
    WalletGet,
    WalletPaymentCreated,
)
from models_library.rest_pagination import Page
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from simcore_service_webserver.payments._api import complete_payment
from simcore_service_webserver.payments.errors import PaymentCompletedError
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)

OpenApiDict: TypeAlias = dict[str, Any]


async def test_payment_on_invalid_wallet(
    new_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
):
    assert client.app

    invalid_wallet = 1234
    assert logged_user_wallet.wallet_id != invalid_wallet

    response = await client.post(
        f"/v0/wallets/{invalid_wallet}/payments",
        json={
            "priceDollars": 25,
        },
    )
    data, error = await assert_status(response, web.HTTPForbidden)
    assert data is None
    assert error


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4657"
)
async def test_payments_worfklow(
    new_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
):
    assert client.app
    settings: PaymentsSettings = get_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_messages", autospec=True
    )

    wallet = logged_user_wallet

    # TEST add payment to wallet
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments",
        json={
            "priceDollars": 25,
        },
    )
    data, error = await assert_status(response, web.HTTPCreated)
    assert error is None
    payment = WalletPaymentCreated.parse_obj(data)

    assert payment.payment_id
    assert payment.payment_form_url.host == "some-fake-gateway.com"
    assert payment.payment_form_url.query
    assert payment.payment_form_url.query.endswith(payment.payment_id)

    # Complete
    await complete_payment(
        client.app,
        payment_id=payment.payment_id,
        completion_state=PaymentTransactionState.SUCCESS,
    )

    # check notification
    assert send_message.called
    send_message.assert_called_once()

    # list all payment transactions in all my wallets
    response = await client.get("/v0/wallets/-/payments")
    data, error = await assert_status(response, web.HTTPOk)

    page = parse_obj_as(Page[PaymentTransaction], data)

    assert page.data
    assert page.meta.total == 1
    assert page.meta.offset == 0

    transaction = page.data[0]
    assert transaction.payment_id == payment.payment_id

    # payment was completed successfully
    assert transaction.completed_at is not None
    assert transaction.created_at < transaction.completed_at


async def test_multiple_payments(
    new_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
):
    assert client.app
    settings: PaymentsSettings = get_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_messages", autospec=True
    )

    wallet = logged_user_wallet

    # Create multiple payments and complete some
    num_payments = 10
    payments_successful = []
    payments_pending = []
    payments_cancelled = []

    for n in range(num_payments):
        response = await client.post(
            f"/v0/wallets/{wallet.wallet_id}/payments",
            json={
                "priceDollars": 10 + n,
                "comment": f"payment {n=}",
            },
        )
        data, error = await assert_status(response, web.HTTPCreated)
        assert data
        assert not error
        payment = WalletPaymentCreated.parse_obj(data)

        if n % 2:
            transaction = await complete_payment(
                client.app,
                payment_id=payment.payment_id,
                completion_state=PaymentTransactionState.SUCCESS,
            )
            assert transaction.payment_id == payment.payment_id
            payments_successful.append(transaction.payment_id)
        else:
            payments_pending.append(payment.payment_id)

    # cancel pending
    pending_id = payments_pending.pop()
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments/{pending_id}:cancel",
    )
    await assert_status(response, web.HTTPNoContent)
    payments_cancelled.append(pending_id)

    assert (
        len(payments_cancelled) + len(payments_successful) + len(payments_pending)
        == num_payments
    )

    # list
    response = await client.get("/v0/wallets/-/payments")
    data, error = await assert_status(response, web.HTTPOk)

    page = parse_obj_as(Page[PaymentTransaction], data)

    assert page.meta.total == num_payments
    all_transactions = {t.payment_id: t for t in page.data}

    for pid in payments_cancelled:
        assert all_transactions[pid].state == PaymentTransactionState.CANCELED
    for pid in payments_successful:
        assert all_transactions[pid].state == PaymentTransactionState.SUCCESS
    for pid in payments_pending:
        assert all_transactions[pid].state == PaymentTransactionState.PENDING

    assert send_message.called


async def test_complete_payment_errors(
    new_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
):
    assert client.app
    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_messages", autospec=True
    )

    wallet = logged_user_wallet

    # Pay
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments",
        json={"priceDollars": 25},
    )
    data, _ = await assert_status(response, web.HTTPCreated)
    payment = WalletPaymentCreated.parse_obj(data)

    # Cannot complete as PENDING
    with pytest.raises(ValueError):
        await complete_payment(
            client.app,
            payment_id=payment.payment_id,
            completion_state=PaymentTransactionState.PENDING,
        )
    send_message.assert_not_called()

    # Complete w/ failures
    await complete_payment(
        client.app,
        payment_id=payment.payment_id,
        completion_state=PaymentTransactionState.FAILED,
    )
    send_message.assert_called_once()

    # Cannot complete twice
    with pytest.raises(PaymentCompletedError):
        await complete_payment(
            client.app,
            payment_id=payment.payment_id,
            completion_state=PaymentTransactionState.SUCCESS,
        )
    send_message.assert_called_once()


async def test_payment_not_found(
    new_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    faker: Faker,
):
    wallet = logged_user_wallet
    payment_id = faker.uuid4()

    # cancel inexistent payment
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments/{payment_id}:cancel",
    )

    data, error = await assert_status(response, web.HTTPNotFound)
    assert data is None
    error_msg = error["errors"][0]["message"]
    assert payment_id in error_msg
    assert ":cancel" not in error_msg


def test_models_state_in_sync():
    state_type = PaymentTransaction.__fields__["state"].type_
    assert (
        parse_obj_as(list[state_type], [f"{s}" for s in PaymentTransactionState])
        is not None
    )


async def test_payment_on_wallet_without_access(
    new_osparc_price: Decimal,
    logged_user_wallet: WalletGet,
    client: TestClient,
):
    other_wallet = logged_user_wallet

    async with LoggedUser(client) as new_logged_user:
        response = await client.post(
            f"/v0/wallets/{other_wallet.wallet_id}/payments",
            json={
                "priceDollars": 25,
            },
        )
        data, error = await assert_status(response, web.HTTPForbidden)
        assert data is None
        assert error

        error_msg = error["errors"][0]["message"]
        assert f"{other_wallet.wallet_id}" in error_msg
