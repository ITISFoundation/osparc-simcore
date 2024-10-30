# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from decimal import Decimal
from typing import Any, TypeAlias
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    PaymentTransaction,
    WalletGet,
    WalletPaymentInitiated,
)
from models_library.rest_pagination import Page
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from simcore_service_webserver.payments._onetime_api import (
    _ack_creation_of_wallet_payment,
)
from simcore_service_webserver.payments.errors import PaymentCompletedError
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)
from simcore_service_webserver.wallets._constants import (
    MSG_BILLING_DETAILS_NOT_DEFINED_ERROR,
)

OpenApiDict: TypeAlias = dict[str, Any]


async def test_payment_on_invalid_wallet(
    latest_osparc_price: Decimal,
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
    data, error = await assert_status(response, status.HTTP_403_FORBIDDEN)
    assert data is None
    assert error


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/issues/4657"
)
@pytest.mark.parametrize(
    "amount_usd,expected_status",
    [(1, status.HTTP_422_UNPROCESSABLE_ENTITY), (25, status.HTTP_201_CREATED)],
)
async def test_one_time_payment_worfklow(
    latest_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
    faker: Faker,
    mock_rpc_payments_service_api: dict[str, MagicMock],
    setup_user_pre_registration_details_db: None,
    amount_usd: int,
    expected_status: int,
):
    assert client.app
    settings: PaymentsSettings = get_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_message_to_user",
        autospec=True,
    )
    mock_rut_add_credits_to_wallet = mocker.patch(
        "simcore_service_webserver.payments._onetime_api.add_credits_to_wallet",
        autospec=True,
    )

    wallet = logged_user_wallet

    # TEST add payment to wallet
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments",
        json={
            "priceDollars": amount_usd,
        },
    )
    data, error = await assert_status(response, expected_status)

    if not error:
        payment = WalletPaymentInitiated.model_validate(data)

        assert payment.payment_id
        assert payment.payment_form_url
        assert payment.payment_form_url.host == "some-fake-gateway.com"
        assert payment.payment_form_url.query
        assert payment.payment_form_url.query.endswith(payment.payment_id)
        assert mock_rpc_payments_service_api["init_payment"].called

        # Complete
        await _ack_creation_of_wallet_payment(
            client.app,
            payment_id=payment.payment_id,
            completion_state=PaymentTransactionState.SUCCESS,
            invoice_url=faker.url(),
        )

        # check notification to RUT (fake)
        assert mock_rut_add_credits_to_wallet.called
        mock_rut_add_credits_to_wallet.assert_called_once()

        # check notification (fake)
        assert send_message.called
        send_message.assert_called_once()

        # list all payment transactions in all my wallets
        response = await client.get("/v0/wallets/-/payments")
        data, error = await assert_status(response, status.HTTP_200_OK)

        page = Page[PaymentTransaction].model_validate(data)

        assert page.data
        assert page.meta.total == 1
        assert page.meta.offset == 0

        transaction = page.data[0]
        assert transaction.payment_id == payment.payment_id

        # payment was completed successfully
        assert transaction.completed_at is not None
        assert transaction.created_at < transaction.completed_at
        assert transaction.invoice_url is not None

        # Get invoice link
        response = await client.get(
            f"/v0/wallets/{wallet.wallet_id}/payments/{payment.payment_id}/invoice-link"
        )
        if response.status == status.HTTP_200_OK:
            # checks is a redirection
            assert len(response.history) == 1
            assert response.history[0].status == status.HTTP_302_FOUND


async def test_multiple_payments(
    latest_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
    faker: Faker,
    mock_rpc_payments_service_api: dict[str, MagicMock],
    setup_user_pre_registration_details_db: None,
):
    assert client.app
    settings: PaymentsSettings = get_plugin_settings(client.app)

    assert settings.PAYMENTS_FAKE_COMPLETION is False

    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_message_to_user",
        autospec=True,
    )
    mocker.patch(
        "simcore_service_webserver.payments._onetime_api.add_credits_to_wallet",
        autospec=True,
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
        data, error = await assert_status(response, status.HTTP_201_CREATED)
        assert data
        assert not error
        payment = WalletPaymentInitiated.model_validate(data)

        if n % 2:
            transaction = await _ack_creation_of_wallet_payment(
                client.app,
                payment_id=payment.payment_id,
                completion_state=PaymentTransactionState.SUCCESS,
                invoice_url=faker.url(),
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
    await assert_status(response, status.HTTP_204_NO_CONTENT)
    assert mock_rpc_payments_service_api["cancel_payment"].called

    payments_cancelled.append(pending_id)

    assert (
        len(payments_cancelled) + len(payments_successful) + len(payments_pending)
        == num_payments
    )

    # list
    response = await client.get("/v0/wallets/-/payments")
    data, error = await assert_status(response, status.HTTP_200_OK)

    page = Page[PaymentTransaction].model_validate(data)

    assert page.meta.total == num_payments
    all_transactions = {t.payment_id: t for t in page.data}

    for pid in payments_cancelled:
        assert all_transactions[pid].state == PaymentTransactionState.CANCELED
        assert all_transactions[pid].invoice_url is None
        assert not PaymentTransactionState(
            all_transactions[pid].state
        ).is_acknowledged()
        assert PaymentTransactionState(all_transactions[pid].state).is_completed()
    for pid in payments_successful:
        assert all_transactions[pid].state == PaymentTransactionState.SUCCESS
        assert all_transactions[pid].invoice_url is not None
        assert PaymentTransactionState(all_transactions[pid].state).is_acknowledged()
        assert PaymentTransactionState(all_transactions[pid].state).is_completed()
    for pid in payments_pending:
        assert all_transactions[pid].state == PaymentTransactionState.PENDING
        assert all_transactions[pid].invoice_url is None
        assert not PaymentTransactionState(
            all_transactions[pid].state
        ).is_acknowledged()
        assert not PaymentTransactionState(all_transactions[pid].state).is_completed()

    assert send_message.called


async def test_complete_payment_errors(
    latest_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    mocker: MockerFixture,
    mock_rpc_payments_service_api: dict[str, MagicMock],
    setup_user_pre_registration_details_db: None,
):
    assert client.app
    send_message = mocker.patch(
        "simcore_service_webserver.payments._socketio.send_message_to_user",
        autospec=True,
    )

    wallet = logged_user_wallet

    # Pay
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments",
        json={"priceDollars": 25},
    )

    assert mock_rpc_payments_service_api["init_payment"].called

    data, _ = await assert_status(response, status.HTTP_201_CREATED)
    payment = WalletPaymentInitiated.model_validate(data)

    # Cannot complete as PENDING
    with pytest.raises(ValueError):
        await _ack_creation_of_wallet_payment(
            client.app,
            payment_id=payment.payment_id,
            completion_state=PaymentTransactionState.PENDING,
        )
    send_message.assert_not_called()

    # Complete w/ failures
    await _ack_creation_of_wallet_payment(
        client.app,
        payment_id=payment.payment_id,
        completion_state=PaymentTransactionState.FAILED,
    )
    send_message.assert_called_once()

    # Cannot complete twice
    with pytest.raises(PaymentCompletedError):
        await _ack_creation_of_wallet_payment(
            client.app,
            payment_id=payment.payment_id,
            completion_state=PaymentTransactionState.SUCCESS,
        )
    send_message.assert_called_once()


async def test_billing_info_missing_error(
    latest_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
):
    # NOTE: setup_user_pre_registration_details_db is not setup to emulate missing pre-registration

    assert client.app
    wallet = logged_user_wallet

    # Pay
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments", json={"priceDollars": 25}
    )
    data, error = await assert_status(response, status.HTTP_503_SERVICE_UNAVAILABLE)

    assert not data
    assert MSG_BILLING_DETAILS_NOT_DEFINED_ERROR in error["message"]

    assert response.reason
    assert MSG_BILLING_DETAILS_NOT_DEFINED_ERROR in response.reason


async def test_payment_not_found(
    latest_osparc_price: Decimal,
    client: TestClient,
    logged_user_wallet: WalletGet,
    faker: Faker,
    mock_rpc_payments_service_api: dict[str, MagicMock],
):
    wallet = logged_user_wallet
    payment_id = faker.uuid4()

    # cancel inexistent payment
    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments/{payment_id}:cancel",
    )
    assert mock_rpc_payments_service_api["cancel_payment"].called

    data, error = await assert_status(response, status.HTTP_404_NOT_FOUND)
    assert data is None
    error_msg = error["errors"][0]["message"]
    assert payment_id in error_msg
    assert ":cancel" not in error_msg


def test_payment_transaction_state_and_literals_are_in_sync():
    state_literals = PaymentTransaction.model_fields["state"].annotation
    assert (
        TypeAdapter(list[state_literals]).validate_python(
            [f"{s}" for s in PaymentTransactionState]
        )
        is not None
    )


async def test_payment_on_wallet_without_access(
    latest_osparc_price: Decimal,
    logged_user: UserInfoDict,
    logged_user_wallet: WalletGet,
    client: TestClient,
):
    wallet = logged_user_wallet

    async with LoggedUser(client) as other_user:
        assert other_user["email"] != logged_user["email"]
        response = await client.post(
            f"/v0/wallets/{wallet.wallet_id}/payments",
            json={
                "priceDollars": 25,
            },
        )
        data, error = await assert_status(response, status.HTTP_403_FORBIDDEN)
        assert data is None
        assert error

        error_msg = error["errors"][0]["message"]
        assert f"{wallet.wallet_id}" in error_msg


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4897"
)
async def test_cannot_get_payment_info_in_shared_wallet(
    latest_osparc_price: Decimal,
    logged_user: UserInfoDict,
    logged_user_wallet: WalletGet,
    client: TestClient,
):
    assert client.app

    async with NewUser(app=client.app) as new_user:
        assert new_user["email"] != logged_user["email"]

        # logged client adds new user to this wallet add read-only
        await assert_status(
            await client.post(
                client.app.router["create_wallet_group"]
                .url_for(
                    wallet_id=f"{logged_user_wallet.wallet_id}",
                    group_id=f"{new_user['primary_gid']}",
                )
                .path,
                json={"read": True, "write": False, "delete": False},
            ),
            status.HTTP_201_CREATED,
        )

        # let's logout one user
        await assert_status(
            await client.post(client.app.router["auth_logout"].url_for().path),
            status.HTTP_200_OK,
        )

        # logs in
        await assert_status(
            await client.post(
                client.app.router["auth_login"].url_for().path,
                json={
                    "email": new_user["email"],
                    "password": new_user["raw_password"],
                },
            ),
            status.HTTP_200_OK,
        )

        # TEST auto-recharge must not be allowed!
        await assert_status(
            await client.get(
                f"/v0/wallets/{logged_user_wallet.wallet_id}/auto-recharge"
            ),
            status.HTTP_403_FORBIDDEN,
        )
