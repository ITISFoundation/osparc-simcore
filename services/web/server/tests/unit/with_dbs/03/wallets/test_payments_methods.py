# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.wallets import (
    CreatePaymentMethodInitiated,
    PaymentMethodGet,
    WalletGet,
)
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.payments._api import complete_payment_method
from simcore_service_webserver.payments.settings import (
    PaymentsSettings,
    get_plugin_settings,
)


@pytest.fixture
def user_role():
    return UserRole.USER


@pytest.fixture
def create_new_wallet(client: TestClient, faker: Faker) -> Callable:
    assert client.app
    url = client.app.router["create_wallet"].url_for()

    async def _create():
        resp = await client.post(
            url.path,
            json={
                "name": f"wallet {faker.word()}",
                "description": "Fake wallet from create_new_wallet",
            },
        )
        data, _ = await assert_status(resp, web.HTTPCreated)
        return WalletGet.parse_obj(data)

    return _create


@pytest.fixture
async def logged_user_wallet(
    client: TestClient,
    logged_user: UserInfoDict,
    wallets_clean_db: None,
    create_new_wallet: Callable,
) -> WalletGet:
    assert client.app
    return await create_new_wallet()


async def test_add_payment_method_worfklow(
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

    response = await client.post(
        f"/v0/wallets/{wallet.wallet_id}/payments-method:init",
    )
    data, error = await assert_status(response, web.HTTPCreated)
    assert error is None
    init = CreatePaymentMethodInitiated.parse_obj(data)

    assert init.payment_method_id
    assert init.payment_method_form_url.query
    assert init.payment_method_form_url.query.endswith(init.payment_method_id)

    # if I try to get the payment method here, it should fail with not completed!
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}"
    )
    data, error = await assert_status(response, web.HTTPConflict)
    assert "complete" in error["errors"][0]["details"]

    # Complete
    await complete_payment_method(
        client.app,
        payment_method_id=init.payment_method_id,
        completion_state=PaymentTransactionState.SUCCESS,
        message="set in test_add_payment_method_worfklow",
    )

    # check notification
    assert send_message.called
    send_message.assert_called_once()

    # get payment-method for this wallet
    response = await client.get(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}"
    )
    data, _ = await assert_status(response, web.HTTPOk)
    payment_method = PaymentMethodGet(**data)
    assert payment_method.idr == init.payment_method_id

    # list all payment-methods for this wallet
    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-method")
    data, _ = await assert_status(response, web.HTTPOk)

    wallet_payments_methods = parse_obj_as(list[PaymentMethodGet], data)
    assert wallet_payments_methods == [payment_method]

    # delete
    response = await client.delete(
        f"/v0/wallets/{wallet.wallet_id}/payments-method/{init.payment_method_id}"
    )
    await assert_status(response, web.HTTPNoContent)

    response = await client.get(f"/v0/wallets/{wallet.wallet_id}/payments-method")
    data, _ = await assert_status(response, web.HTTPOk)
    assert not data
